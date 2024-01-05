import pendulum
from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    define_asset_job,
    schedule,
)
from sqlalchemy import text

from teamster.core.sqlalchemy.resources import OracleResource
from teamster.core.ssh.resources import SSHResource


def build_powerschool_schedule(
    code_location, cron_schedule, execution_timezone, asset_defs: list[AssetsDefinition]
):
    job_name = f"{code_location}_powerschool_schedule_job"

    job = define_asset_job(
        name=job_name, selection=asset_defs, tags={MAX_RUNTIME_SECONDS_TAG: (60 * 10)}
    )

    schedule_name = f"{job_name}_schedule"

    @schedule(
        cron_schedule=cron_schedule,
        name=schedule_name,
        execution_timezone=execution_timezone,
        job=job,
    )  # type: ignore
    def _schedule(
        context: ScheduleEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ) -> RunRequest | None:
        ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

        try:
            context.log.info("Starting SSH tunnel")
            ssh_tunnel.start()

            asset_selection = []
            for asset in asset_defs:
                context.log.info(asset.key)

                is_requested = False

                latest_materialization_event = (
                    context.instance.get_latest_materialization_event(asset.key)
                )

                latest_materialization_timestamp = (
                    latest_materialization_event.asset_materialization.metadata.get(
                        "latest_materialization_timestamp"
                    )
                    if latest_materialization_event is not None
                    else None
                )

                latest_materialization_datetime = pendulum.from_timestamp(
                    timestamp=(
                        latest_materialization_timestamp.value
                        if latest_materialization_timestamp is not None
                        else 0.0
                    )  # type: ignore
                ).start_of("minute")

                if latest_materialization_datetime.timestamp() == 0:
                    is_requested = True
                else:
                    partition_column = asset.metadata_by_key[asset.key][
                        "partition_column"
                    ]

                    latest_materialization_fmt = (
                        latest_materialization_datetime.in_timezone(
                            execution_timezone
                        ).format("YYYY-MM-DDTHH:mm:ss.SSSSSS")
                    )

                    [(count,)] = db_powerschool.engine.execute_query(
                        query=text(
                            # trunk-ignore(bandit/B608)
                            "SELECT COUNT(*) "
                            f"FROM {asset.key.path[-1]} "
                            f"WHERE {partition_column} >= "
                            f"TO_TIMESTAMP('{latest_materialization_fmt}', "
                            "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
                        ),
                        partition_size=1,
                        output_format=None,
                    )  # type: ignore

                    context.log.info(f"count: {count}")

                    if int(count) > 0:
                        is_requested = True

                if is_requested:
                    asset_selection.append(asset.key)

        finally:
            context.log.info("Stopping SSH tunnel")
            ssh_tunnel.stop()

        if asset_selection:
            return RunRequest(run_key=schedule_name, asset_selection=asset_selection)

    return _schedule
