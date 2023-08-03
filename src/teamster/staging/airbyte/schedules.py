from dagster import ScheduleDefinition

from .. import LOCAL_TIMEZONE
from .jobs import airbyte_start_sync_jobs

__all__ = []

for job in airbyte_start_sync_jobs:
    __all__.append(
        ScheduleDefinition(
            cron_schedule="0 0 * * *", job=job, execution_timezone=LOCAL_TIMEZONE.name
        )
    )
