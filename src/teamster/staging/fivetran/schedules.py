from dagster import ScheduleDefinition

from teamster.staging import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.staging.fivetran.jobs import (
    fivetran_start_resync_jobs,
    fivetran_start_sync_jobs,
)

adp_wfn_resync_schedule = ScheduleDefinition(
    cron_schedule="0 20 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=[
        job
        for job in fivetran_start_resync_jobs
        if job.name == f"{CODE_LOCATION}_adp_workforce_now_fivetran_start_resync_job"
    ][0],
)

__all__ = [
    adp_wfn_resync_schedule,
]

for job in fivetran_start_sync_jobs:
    if job.name == f"{CODE_LOCATION}_adp_workforce_now_fivetran_start_sync_job":
        cron_schedule = "0 0-19 * * *"
    else:
        cron_schedule = "0 * * * *"

    __all__.append(
        ScheduleDefinition(
            cron_schedule=cron_schedule, execution_timezone=LOCAL_TIMEZONE.name, job=job
        )
    )
