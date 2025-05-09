from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.knowbe4.assets import assets

knowbe4_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__knowbe4__asset_job_schedule",
    target=assets,
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    knowbe4_asset_job_schedule,
]
