from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.smartrecruiters.assets import assets

smartrecruiters_report_assets_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__smartrecruiters__assets_schedule",
    target=assets,
    cron_schedule="0 6 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    tags={MAX_RUNTIME_SECONDS_TAG: str(60 * 10)},
)

schedules = [
    smartrecruiters_report_assets_schedule,
]
