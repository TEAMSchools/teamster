import json
import os

import pendulum
from dagster import (
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


def get_asset_count(asset, db, window_start):
    partition_column = asset.metadata_by_key[asset.key]["partition_column"]

    # window_end_fmt = window_end.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")
    window_start_fmt = window_start.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

    query = text(
        text=" ".join(
            [
                "SELECT COUNT(*)",
                f"FROM {asset.asset_key.path[-1]}",
                f"WHERE {partition_column} >=",
                f"TO_TIMESTAMP('{window_start_fmt}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')",
            ]
        )
    )

    [(count,)] = db.execute_query(
        query=query,
        partition_size=1,
        output=None,
    )

    return count


def build_dynamic_partition_sensor(
    name,
    asset_selection,
    partitions_def,
    minimum_interval_seconds=None,
):
    asset_job = define_asset_job(
        name="powerschool_asset_dynamic_partition_job",
        selection=asset_selection,
        partitions_def=partitions_def,
    )

    @sensor(
        name=name,
        job=asset_job,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(context: SensorEvaluationContext):
        window_end: pendulum.DateTime = (
            pendulum.now(tz=LOCAL_TIME_ZONE)
            .subtract(minutes=5)  # 5 min grace period for PS lag
            .start_of("minute")
        )

        cursor = json.loads(context.cursor or "{}")
        asset_defs = [
            a
            for a in context.repository_def.asset_graph.assets
            if a.key in asset_selection._keys
        ]

        # check if asset has ever been materialized
        never_materialized = set(
            asset
            for asset in asset_defs
            if not context.instance.get_latest_materialization_event(asset.key)
        )
        to_check = set(
            asset
            for asset in asset_defs
            if context.instance.get_latest_materialization_event(asset.key)
        )

        if never_materialized:
            context.log.debug(
                [asset.key.to_python_identifier() for asset in never_materialized]
            )
            context.log.debug("RESYNC")

            window_start = pendulum.from_timestamp(0).replace(tzinfo=LOCAL_TIME_ZONE)

            partitions_def.add_partitions(
                partition_keys=[window_start.to_iso8601_string()],
                instance=context.instance,
            )

            yield asset_job.run_request_for_partition(
                run_key=f"powerschool_resync_{window_start.int_timestamp}",
                partition_key=window_start.to_iso8601_string(),
                run_config={
                    "execution": {
                        "config": {
                            "resources": {"limits": {"cpu": "750m", "memory": "1.0Gi"}}
                        }
                    }
                },
                instance=context.instance,
                asset_selection=[asset.key for asset in never_materialized],
            )

            for asset in never_materialized:
                cursor[asset.key.to_python_identifier()] = window_end.timestamp()

        # check if asset has any modified records from past X hours
        run_request_data = []

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
                for asset in to_check:
                    asset_key_string = asset.key.to_python_identifier()
                    context.log.debug(asset_key_string)

                    cursor_window_start = cursor.get(asset_key_string)

                    if cursor_window_start:
                        window_start = pendulum.from_timestamp(
                            cursor_window_start, tz=LOCAL_TIME_ZONE
                        )
                    else:
                        window_start: pendulum.DateTime = window_end.subtract(
                            weeks=1  # rewind 1 week in case of manual cursor reset
                        ).start_of("day")
                        cursor[asset_key_string] = window_start.timestamp()

                    context.log.debug(
                        window_start.to_iso8601_string()
                        + " - "
                        + window_end.to_iso8601_string()
                    )

                    count = get_asset_count(
                        asset=asset, db=resources.db, window_start=window_start
                    )

                    context.log.debug(f"count: {count}")
                    if count > 0:
                        run_request_data.append(
                            {"asset": asset, "window_start": window_start}
                        )

                        cursor[asset_key_string] = window_end.timestamp()
            finally:
                context.log.debug("Stopping SSH tunnel")
                ssh_tunnel.stop()

        # get unique window starts
        window_starts = list(set([rr["window_start"] for rr in run_request_data]))

        partitions_def.add_partitions(
            partition_keys=[ws.to_iso8601_string() for ws in window_starts],
            instance=context.instance,
        )

        # group run requests by window start
        for window_start in window_starts:
            run_request_data_filtered = [
                rr for rr in run_request_data if rr["window_start"] == window_start
            ]

            yield asset_job.run_request_for_partition(
                run_key=f"powerschool_dynamic_partition_{window_start.int_timestamp}",
                partition_key=window_start.to_iso8601_string(),
                instance=context.instance,
                asset_selection=[rr["asset"].key for rr in run_request_data_filtered],
            )

        context.update_cursor(json.dumps(cursor))

    return _sensor
