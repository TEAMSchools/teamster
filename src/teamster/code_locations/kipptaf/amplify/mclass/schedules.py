from dagster import RunRequest, schedule

from teamster.code_locations.kipptaf import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kipptaf.amplify.mclass.jobs import mclass_asset_job


@schedule(
    cron_schedule="0 4 * * *",
    name=f"{CODE_LOCATION}_{mclass_asset_job.name}",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=mclass_asset_job,
)
def mclass_asset_job_schedule():
    partition_key = CURRENT_FISCAL_YEAR.start.to_date_string()

    yield RunRequest(
        run_key=f"{CODE_LOCATION}_{mclass_asset_job.name}_{partition_key}",
        partition_key=partition_key,
    )


schedules = [
    mclass_asset_job_schedule,
]
