from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE

from . import jobs

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=jobs.powerschool_extract_asset_job,
    cron_schedule="15 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

__all__ = [powerschool_extract_assets_schedule]
