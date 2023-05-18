from dagster import ScheduleDefinition

from .. import LOCAL_TIMEZONE
from .jobs import cpn_extract_asset_job, powerschool_extract_asset_job

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_asset_job,
    cron_schedule="15 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

cpn_extract_assets_schedule = ScheduleDefinition(
    job=cpn_extract_asset_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

__all__ = [
    cpn_extract_assets_schedule,
    powerschool_extract_assets_schedule,
]
