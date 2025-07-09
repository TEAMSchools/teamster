from dagster import (
    RunRequest,
    ScheduleDefinition,
    ScheduleEvaluationContext,
    schedule,
)
from dagster_shared import check

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_now.api.assets import (
    adp_workforce_now_workers,
    adp_workforce_now_workers_update,
)

adp_workforce_now_workers_sync_schedule = ScheduleDefinition(
    # trunk-ignore(pyright/reportFunctionMemberAccess)
    name=f"{adp_workforce_now_workers_update.key.to_python_identifier()}_schedule",
    # trunk-ignore(pyright/reportArgumentType)
    target=adp_workforce_now_workers_update,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)


@schedule(
    # trunk-ignore(pyright/reportFunctionMemberAccess)
    name=f"{adp_workforce_now_workers.key.to_python_identifier()}_schedule",
    # trunk-ignore(pyright/reportArgumentType)
    target=adp_workforce_now_workers,
    cron_schedule="30 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)
def adp_workforce_now_api_workers_asset_schedule(context: ScheduleEvaluationContext):
    # trunk-ignore(pyright/reportFunctionMemberAccess)
    partitions_def = check.not_none(adp_workforce_now_workers.partitions_def)

    partition_keys = partitions_def.get_partition_keys()

    # materialize +2 weeks & -1 month
    for partition_key in partition_keys[-45:]:
        yield RunRequest(
            run_key=f"{context._schedule_name}_{partition_key}",
            partition_key=partition_key.format(fmt="%m/%d/%Y"),
        )


schedules = [
    adp_workforce_now_workers_sync_schedule,
    adp_workforce_now_api_workers_asset_schedule,
]
