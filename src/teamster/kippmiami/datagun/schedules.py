from dagster import ScheduleDefinition

from .. import LOCAL_TIMEZONE
from .jobs import powerschool_extract_asset_job

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_asset_job,
    cron_schedule="15 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

_all = [
    powerschool_extract_assets_schedule,
]
