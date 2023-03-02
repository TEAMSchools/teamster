import json
import os

import pendulum
from dagster import (
    DynamicPartitionsDefinition,
    SensorEvaluationContext,
    build_resources,
    config_from_files,
    define_asset_job,
    sensor,
)
from dagster_ssh import ssh_resource
from sqlalchemy import text

from teamster.core.resources.sqlalchemy import oracle
from teamster.core.utils.variables import LOCAL_TIME_ZONE


def get_asset_count(asset, db, window_start, window_end):
    partition_column = asset.metadata_by_key[asset.key]["partition_column"]

    window_end_fmt = window_end.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")
    window_start_fmt = window_start.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

    query = text(
        text=" ".join(
            [
                "SELECT COUNT(*)",
                f"FROM {asset.asset_key.path[-1]}",
                f"WHERE {partition_column} >=",
                f"TO_TIMESTAMP('{window_start_fmt}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')",
                f"AND {partition_column} <",
                f"TO_TIMESTAMP('{window_end_fmt}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')",
            ]
        )
    )

    [(count,)] = db.execute_query(
        query=query,
        partition_size=1,
        output=None,
    )

    return count


def build_dynamic_parition_sensor(
    name,
    asset_selection,
    minimum_interval_seconds=None,
    partitions_def=DynamicPartitionsDefinition(name="partition_column"),
):
    @sensor(
        name=name,
        asset_selection=asset_selection,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(context: SensorEvaluationContext):
        cursor = json.loads(context.cursor or "{}")
        asset_graph = context.repository_def.asset_graph

        # check if asset has ever been materialized or requested
        never_materialized = set(
            asset_key
            for asset_key in asset_selection.resolve(asset_graph.assets)
            if not context.instance.get_latest_materialization_event(asset_key)
        )
        context.log.info(never_materialized)

        # check if asset has any modified records from past X hours
        with build_resources(
            resources={"ssh": ssh_resource, "db": oracle},
            resource_config={
                "ssh": {
                    "config": config_from_files(
                        ["src/teamster/core/resources/config/ssh_powerschool.yaml"]
                    )
                },
                "db": {
                    "config": config_from_files(
                        ["src/teamster/core/resources/config/db_powerschool.yaml"]
                    )
                },
            },
        ) as resources:
            ssh_port = 1521
            ssh_tunnel = resources.ssh.get_tunnel(
                remote_port=ssh_port,
                remote_host=os.getenv("PS_SSH_REMOTE_BIND_HOST"),
                local_port=ssh_port,
            )

            ssh_tunnel.check_tunnels()
            if ssh_tunnel.tunnel_is_up.get(("127.0.0.1", ssh_port)):
                context.log.debug("Restarting SSH tunnel")
                ssh_tunnel.restart()
            else:
                context.log.debug("Starting SSH tunnel")
                ssh_tunnel.start()

            try:
                asset_defs = [
                    a for a in asset_graph.assets if a.key in asset_selection._keys
                ]
                for asset in asset_defs:
                    window_end: pendulum.DateTime = (
                        pendulum.now(tz=LOCAL_TIME_ZONE.name)
                        .subtract(minutes=5)
                        .start_of("minute")
                    )
                    asset_key_string = asset.key.to_python_identifier()

                    cursor_window_start = cursor.get(asset_key_string)
                    if cursor_window_start:
                        window_start = pendulum.from_timestamp(
                            cursor_window_start, tz=LOCAL_TIME_ZONE.name
                        )
                    else:
                        window_start: pendulum.DateTime = window_end.subtract(
                            days=1
                        ).start_of("day")
                        cursor[asset_key_string] = window_start.timestamp()

                    count = get_asset_count(
                        asset=asset,
                        db=resources.db,
                        window_start=window_start,
                        window_end=window_end,
                    )

                    context.log.debug(f"count: {count}")
                    if count > 0:
                        partitions_def.add_partitions(
                            partition_keys=[window_end.to_iso8601_string()],
                            instance=context.instance,
                        )

                        asset_job = define_asset_job(
                            name=asset_key_string,
                            selection=[asset.key],
                            partitions_def=partitions_def,
                        )

                        yield asset_job.run_request_for_partition(
                            run_key=f"{asset_key_string}_{window_start.int_timestamp}",
                            partition_key=window_end.to_iso8601_string(),
                            instance=context.instance,
                        )

                        cursor[asset_key_string] = window_end.timestamp()
            finally:
                context.log.info("Stopping SSH tunnel")
                ssh_tunnel.stop()

        context.update_cursor(json.dumps(cursor))

    return _sensor
