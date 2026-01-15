from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.coupa.assets import assets

coupa_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__coupa__asset_job_schedule",
    target=assets,
    cron_schedule="0 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    coupa_asset_job_schedule,
]
