from dagster import ScheduleDefinition

from .. import LOCAL_TIMEZONE
from .jobs import fivetran_start_sync_jobs

__all__ = []

for job in fivetran_start_sync_jobs:
    __all__.append(
        ScheduleDefinition(
            cron_schedule="0 * * * *",
            job=job,
            execution_timezone=LOCAL_TIMEZONE.name,
        )
    )
