from typing import Generator

from dagster import (
    RunRequest,
    ScheduleDefinition,
    ScheduleEvaluationContext,
    _check,
    define_asset_job,
    schedule,
)

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_now.api.assets import workers
from teamster.code_locations.kipptaf.adp.workforce_now.api.jobs import (
    adp_wfn_update_workers_job,
)

adp_wfn_worker_fields_update_schedule = ScheduleDefinition(
    job=adp_wfn_update_workers_job,
    cron_schedule="0 6* * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

job = define_asset_job(
    name=f"{CODE_LOCATION}_adp_workforce_now_api_workers_asset_job",
    selection=[workers],
    partitions_def=workers.partitions_def,
)


@schedule(
    name=f"{job.name}_schedule",
    job=job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)
def adp_wfn_api_workers_asset_schedule(context: ScheduleEvaluationContext) -> Generator:
    partitions_def = _check.not_none(job.partitions_def)

    partition_keys = partitions_def.get_partition_keys()

    # materialize +/- 2 weeks
    for partition_key in partition_keys[-31:]:
        yield RunRequest(
            run_key=f"{context._schedule_name}_{partition_key}",
            partition_key=partition_key.format(fmt="MM/DD/YYYY"),
        )


schedules = [
    adp_wfn_worker_fields_update_schedule,
    adp_wfn_api_workers_asset_schedule,
]
