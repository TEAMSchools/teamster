import json
import os

import pendulum
from dagster import (
    AssetsDefinition,
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

    [(count,)] = db.execute_query(query=query, partition_size=1, output=None)

    return count


def build_dynamic_partition_sensor(
    code_location,
    name,
    asset_defs: list[AssetsDefinition],
    minimum_interval_seconds=None,
):
    asset_jobs = [
        define_asset_job(
            name=asset.key.to_python_identifier(),
            selection=[asset],
            partitions_def=asset.partitions_def,
        )
        for asset in asset_defs
    ]

    @sensor(
        name=name, jobs=asset_jobs, minimum_interval_seconds=minimum_interval_seconds
    )
    def _sensor(context: SensorEvaluationContext):
        window_end: pendulum.DateTime = (
            pendulum.now(tz=LOCAL_TIME_ZONE)
            .subtract(minutes=5)  # 5 min grace period for PS lag
            .start_of("minute")
        )

        cursor = json.loads(context.cursor or "{}")

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

            window_start = pendulum.from_timestamp(0)

            for asset in never_materialized:
                context.instance.add_dynamic_partitions(
                    partitions_def_name=asset.partitions_def.name,
                    partition_keys=[window_start.to_iso8601_string()],
                )

                asset_job = [
                    job
                    for job in asset_jobs
                    if job.name == asset.key.to_python_identifier()
                ][0]

                yield asset_job.run_request_for_partition(
                    run_key=f"{asset_job.name}_resync",
                    partition_key=window_start.to_iso8601_string(),
                    run_config={
                        "execution": {
                            "config": {
                                "resources": {
                                    "limits": {"cpu": "750m", "memory": "1.0Gi"}
                                }
                            }
                        }
                    },
                    instance=context.instance,
                    asset_selection=[asset.key for asset in never_materialized],
                )

                cursor[asset.key.to_python_identifier()] = window_end.timestamp()

        # check if asset has any modified records from past X hours
        local_config_dir = f"src/teamster/{code_location}/config/resources"
        with build_resources(
            resources={"ssh": ssh_resource, "db": oracle},
            resource_config={
                "ssh": {
                    "config": config_from_files(
                        [f"{local_config_dir}/ssh_powerschool.yaml"]
                    )
                },
                "db": {
                    "config": config_from_files(
                        [
                            "src/teamster/core/config/resources/db_powerschool.yaml",
                            f"{local_config_dir}/db_powerschool.yaml",
                        ]
                    )
                },
            },
        ) as resources:
            ssh_port = 1521
            ssh_tunnel = resources.ssh.get_tunnel(
                remote_port=ssh_port,
                remote_host=os.getenv(
                    f"{code_location.upper()}_PS_SSH_REMOTE_BIND_HOST"
                ),
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
                            weeks=2  # rewind 2 weeks in case of manual cursor reset
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
                        context.instance.add_dynamic_partitions(
                            partitions_def_name=asset.partitions_def.name,
                            partition_keys=[window_start.to_iso8601_string()],
                        )

                        asset_job = [
                            job
                            for job in asset_jobs
                            if job.name == asset.key.to_python_identifier()
                        ][0]

                        yield asset_job.run_request_for_partition(
                            run_key=f"{asset_job.name}_{window_start.int_timestamp}",
                            partition_key=window_start.to_iso8601_string(),
                            instance=context.instance,
                            asset_selection=[asset.key],
                        )

                        cursor[asset_key_string] = window_end.timestamp()
            finally:
                context.log.debug("Stopping SSH tunnel")
                ssh_tunnel.stop()

        context.update_cursor(json.dumps(cursor))

    return _sensor
