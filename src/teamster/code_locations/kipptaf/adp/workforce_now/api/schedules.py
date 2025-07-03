from typing import Generator

from dagster import (
    RunRequest,
    ScheduleDefinition,
    ScheduleEvaluationContext,
    define_asset_job,
    schedule,
)
from dagster_shared import check

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_now.api.assets import (
    adp_workforce_now_workers,
)
from teamster.code_locations.kipptaf.adp.workforce_now.api.jobs import (
    adp_wfn_update_workers_job,
)

adp_wfn_worker_fields_update_schedule = ScheduleDefinition(
    job=adp_wfn_update_workers_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

job = define_asset_job(
    name=f"{CODE_LOCATION}_adp_workforce_now_api_workers_asset_job",
    selection=[adp_workforce_now_workers],
    partitions_def=adp_workforce_now_workers.partitions_def,
)


@schedule(
    name=f"{job.name}_schedule",
    job=job,
    cron_schedule="30 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)
def adp_wfn_api_workers_asset_schedule(context: ScheduleEvaluationContext) -> Generator:
    partitions_def = check.not_none(job.partitions_def)

    partition_keys = partitions_def.get_partition_keys()

    # materialize +2 weeks & -1 month
    for partition_key in partition_keys[-45:]:
        yield RunRequest(
            run_key=f"{context._schedule_name}_{partition_key}",
            partition_key=partition_key.format(fmt="%m/%d/%Y"),
        )


schedules = [
    adp_wfn_worker_fields_update_schedule,
    adp_wfn_api_workers_asset_schedule,
]
