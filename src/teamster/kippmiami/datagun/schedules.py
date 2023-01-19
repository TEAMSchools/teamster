from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE

from .jobs import powerschool_extract_assets_job

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_assets_job,
    cron_schedule="15 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

__all__ = [powerschool_extract_assets_schedule]
