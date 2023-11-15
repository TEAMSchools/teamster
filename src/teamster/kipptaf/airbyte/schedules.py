from dagster import ScheduleDefinition

from .. import LOCAL_TIMEZONE
from .jobs import kipptaf_airbyte_start_syncs_job

__all__ = [
    ScheduleDefinition(
        cron_schedule="0 0 * * *",
        job=kipptaf_airbyte_start_syncs_job,
        execution_timezone=LOCAL_TIMEZONE.name,
    )
]
