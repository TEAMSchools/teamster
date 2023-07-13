from dagster import ScheduleDefinition

from . import jobs

__all__ = []

for job in jobs:
    if job.name == "kipptaf_fivetran_adp_workforce_now_asset_job":
        __all__.append(ScheduleDefinition(cron_schedule="0 * * * *", job=job))
    else:
        __all__.append(ScheduleDefinition(cron_schedule="0 0 * * *", job=job))
