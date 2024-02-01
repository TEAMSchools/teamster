from dagster import ScheduleDefinition

from .. import LOCAL_TIMEZONE
from .jobs import smartrecruiters_report_asset_job

smartrecruiters_report_assets_schedule = ScheduleDefinition(
    job=smartrecruiters_report_asset_job,
    cron_schedule="0 6 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

_all = [
    smartrecruiters_report_assets_schedule,
]
