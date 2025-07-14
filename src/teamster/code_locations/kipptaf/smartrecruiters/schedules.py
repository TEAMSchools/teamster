from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.smartrecruiters.assets import assets

smartrecruiters_report_assets_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__smartrecruiters__assets_schedule",
    target=assets,
    cron_schedule="0 6 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    smartrecruiters_report_assets_schedule,
]
