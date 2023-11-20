import pendulum
from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetMaterialization,
    AssetsDefinition,
    AssetSelection,
    MetadataValue,
    RunRequest,
    ScheduleEvaluationContext,
    define_asset_job,
    schedule,
)
from sqlalchemy import text

from teamster.core.sqlalchemy.resources import OracleResource
from teamster.core.ssh.resources import SSHResource


def build_last_modified_schedule(
    code_location, cron_schedule, execution_timezone, asset_defs: list[AssetsDefinition]
):
    job_name = f"{code_location}_powerschool_last_modified_job"

    job = define_asset_job(
        name=job_name,
        selection=AssetSelection.assets(*asset_defs),
        tags={MAX_RUNTIME_SECONDS_TAG: (60 * 10)},
    )

    schedule_name = f"{job_name}_schedule"

    @schedule(
        cron_schedule=cron_schedule,
        name=schedule_name,
        execution_timezone=execution_timezone,
        job=job,
    )
    def _schedule(
        context: ScheduleEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ):
        ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

        try:
            context.log.info("Starting SSH tunnel")
            ssh_tunnel.start()

            asset_selection = []
            for asset in asset_defs:
                asset_key = asset.key
                context.log.info(asset_key)

                event = context.instance.get_latest_materialization_event(asset_key)

                asset_materialization = (
                    event.asset_materialization
                    if event is not None
                    else AssetMaterialization(
                        asset_key=asset_key,
                        metadata={
                            "latest_materialization_timestamp": MetadataValue.float(0.0)
                        },
                    )
                )

                latest_materialization_timestamp = (
                    asset_materialization.metadata.get(
                        "latest_materialization_timestamp"
                    )
                    or 0.0
                )

                latest_materialization = pendulum.from_timestamp(
                    latest_materialization_timestamp.value
                    if isinstance(latest_materialization_timestamp, MetadataValue)
                    else latest_materialization_timestamp
                )

                is_requested = False
                if latest_materialization.timestamp() == 0:
                    is_requested = True
                else:
                    partition_column = asset.metadata_by_key[asset_key][
                        "partition_column"
                    ]

                    latest_materialization_fmt = latest_materialization.in_timezone(
                        execution_timezone
                    ).format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

                    [(count,)] = db_powerschool.engine.execute_query(
                        query=text(
                            "SELECT COUNT(*) "
                            f"FROM {asset_key.path[-1]} "
                            f"WHERE {partition_column} >= "
                            f"TO_TIMESTAMP('{latest_materialization_fmt}', "
                            "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
                        ),
                        partition_size=1,
                        output_format=None,
                    )

                    context.log.info(f"count: {count}")

                    if count > 0:
                        is_requested = True

                if is_requested:
                    asset_selection.append(asset_key)

        finally:
            context.log.info("Stopping SSH tunnel")
            ssh_tunnel.stop()

        if asset_selection:
            return RunRequest(run_key=schedule_name, asset_selection=asset_selection)

    return _schedule
