from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    RunRequest,
    ScheduleEvaluationContext,
    define_asset_job,
    schedule,
)

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
    execution_timezone=str(LOCAL_TIMEZONE),
    job=mclass_asset_job,
)
def mclass_asset_job_schedule(context: ScheduleEvaluationContext):
    yield RunRequest(
        partition_key=CURRENT_FISCAL_YEAR.start.isoformat(),
        tags={MAX_RUNTIME_SECONDS_TAG: (60 * 10)},
    )


schedules = [
    mclass_asset_job_schedule,
]
