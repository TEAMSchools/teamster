from dagster import RunRequest, ScheduleEvaluationContext, define_asset_job, schedule

from teamster.code_locations.kipptaf import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kipptaf.amplify.mclass.assets import assets

mclass_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__amplify__mclass_asset_job", selection=assets
)


@schedule(
    name=f"{mclass_asset_job.name}_schedule",
    cron_schedule="0 4 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=mclass_asset_job,
)
def mclass_asset_job_schedule(context: ScheduleEvaluationContext):
    yield RunRequest(partition_key=CURRENT_FISCAL_YEAR.start.to_date_string())


schedules = [
    mclass_asset_job_schedule,
]
