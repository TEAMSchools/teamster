import pendulum
from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetMaterialization,
    AssetsDefinition,
    EventLogEntry,
    RunRequest,
    ScheduleEvaluationContext,
    _check,
    define_asset_job,
    schedule,
)
from sqlalchemy import text
from sshtunnel import SSHTunnelForwarder

from teamster.libraries.sqlalchemy.resources import OracleResource
from teamster.libraries.ssh.resources import SSHResource


def build_powerschool_schedule(
    code_location,
    cron_schedule,
    execution_timezone,
    asset_defs: list[AssetsDefinition],
    max_runtime_seconds,
):
    job_name = f"{code_location}_powerschool_schedule_job"

    job = define_asset_job(name=job_name, selection=asset_defs)

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
    ) -> RunRequest | None:
        asset_selection = []

        with ssh_powerschool.get_tunnel(
            remote_port=1521, local_port=1521
        ) as ssh_tunnel:
            ssh_tunnel = _check.inst(ssh_tunnel, SSHTunnelForwarder)

            ssh_tunnel.start()

            for asset in asset_defs:
                context.log.info(asset.key)

                latest_materialization_event = _check.inst(
                    context.instance.get_latest_materialization_event(asset.key),
                    EventLogEntry,
                )

                asset_materialization = _check.inst(
                    latest_materialization_event.asset_materialization,
                    AssetMaterialization,
                )

                latest_materialization_timestamp = (
                    asset_materialization.metadata.get(
                        "latest_materialization_timestamp"
                    )
                    if latest_materialization_event is not None
                    else None
                )

                latest_materialization_datetime = pendulum.from_timestamp(
                    timestamp=(
                        _check.inst(latest_materialization_timestamp.value, float)
                        if latest_materialization_timestamp is not None
                        else 0.0
                    )
                )

                if latest_materialization_datetime.timestamp() == 0:
                    asset_selection.append(asset.key)
                else:
                    partition_column = asset.metadata_by_key[asset.key][
                        "partition_column"
                    ]

                    latest_materialization_fmt = (
                        latest_materialization_datetime.in_timezone(
                            tz=execution_timezone
                        ).format("YYYY-MM-DDTHH:mm:ss.SSSSSS")
                    )

                    [(count,)] = _check.inst(
                        db_powerschool.engine.execute_query(
                            query=text(
                                # trunk-ignore(bandit/B608)
                                f"SELECT COUNT(*) FROM {asset.key.path[-1]} "
                                f"WHERE {partition_column} >= "
                                f"TO_TIMESTAMP('{latest_materialization_fmt}', "
                                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
                            ),
                            partition_size=1,
                            output_format=None,
                        ),
                        list,
                    )

                    context.log.info(f"count: {count}")

                    if int(count) > 0:
                        asset_selection.append(asset.key)

        if asset_selection:
            return RunRequest(
                run_key=schedule_name,
                asset_selection=asset_selection,
                tags={MAX_RUNTIME_SECONDS_TAG: max_runtime_seconds},
            )

    return _schedule
