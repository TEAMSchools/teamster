from dagster import ScheduleDefinition

from .. import LOCAL_TIMEZONE
from . import jobs

__all__ = []

for job in jobs:
    __all__.append(
        ScheduleDefinition(
            cron_schedule="0 0 * * *", job=job, execution_timezone=LOCAL_TIMEZONE.name
        )
    )
