from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.smartrecruiters.jobs import (
    smartrecruiters_report_asset_job,
)

smartrecruiters_report_assets_schedule = ScheduleDefinition(
    job=smartrecruiters_report_asset_job,
    cron_schedule="0 6 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    smartrecruiters_report_assets_schedule,
]
