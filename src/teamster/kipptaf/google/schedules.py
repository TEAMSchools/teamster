from dagster import ScheduleDefinition

from .. import LOCAL_TIMEZONE
from .jobs import google_forms_asset_job

google_forms_asset_job_schedule = ScheduleDefinition(
    job=google_forms_asset_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

__all__ = [
    google_forms_asset_job_schedule,
]
