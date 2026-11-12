from dagster import (
    RunRequest,
    ScheduleDefinition,
    ScheduleEvaluationContext,
    define_asset_job,
    in_process_executor,
    schedule,
)
from dagster_shared import check

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_now.api.assets import (
    adp_workforce_now_workers,
    adp_workforce_now_workers_update,
)

adp_workforce_now_workers_sync_schedule = ScheduleDefinition(
    name=f"{adp_workforce_now_workers_update.key.to_python_identifier()}_schedule",
    target=define_asset_job(
        name=f"{adp_workforce_now_workers_update.key.to_python_identifier()}_asset_job",
        selection=[adp_workforce_now_workers_update],
        executor_def=in_process_executor,
    ),
    cron_schedule="25 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)


# In process: a step pod per partition doubles the 00:30 pod burst that GKE
# preempts on new nodes (#6225). Each partition is still its own run.
adp_workforce_now_workers_asset_job = define_asset_job(
    name=f"{adp_workforce_now_workers.key.to_python_identifier()}_asset_job",
    selection=[adp_workforce_now_workers],
    executor_def=in_process_executor,
)


@schedule(
    name=f"{adp_workforce_now_workers.key.to_python_identifier()}_schedule",
    target=adp_workforce_now_workers_asset_job,
    cron_schedule="30 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)
def adp_workforce_now_api_workers_asset_schedule(context: ScheduleEvaluationContext):
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
