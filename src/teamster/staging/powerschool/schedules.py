from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIMEZONE

from .jobs import powerschool_nonpartition_asset_job

powerschool_nonpartition_asset_job_schedule = ScheduleDefinition(
    job=powerschool_nonpartition_asset_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

__all__ = [
    powerschool_nonpartition_asset_job_schedule,
]
