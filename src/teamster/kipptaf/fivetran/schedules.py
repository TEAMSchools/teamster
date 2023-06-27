from dagster import ScheduleDefinition

from . import jobs

__all__ = []

for job in jobs:
    __all__.append(ScheduleDefinition(cron_schedule="0 * * * *", job=job))
