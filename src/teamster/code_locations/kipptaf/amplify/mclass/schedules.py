from typing import Generator

from dagster import RunRequest, ScheduleEvaluationContext, define_asset_job, schedule

from teamster.code_locations.kipptaf import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kipptaf.amplify.mclass.assets import assets

job = define_asset_job(name=f"{CODE_LOCATION}_mclass_asset_job", selection=assets)


@schedule(
    name=f"{job.name}_schedule",
    cron_schedule="0 4 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=job,
)
def mclass_asset_job_schedule(context: ScheduleEvaluationContext) -> Generator:
    partition_key = CURRENT_FISCAL_YEAR.start.to_date_string()

    yield RunRequest(
        run_key=f"{context._schedule_name}_{partition_key}", partition_key=partition_key
    )


schedules = [
    mclass_asset_job_schedule,
]
