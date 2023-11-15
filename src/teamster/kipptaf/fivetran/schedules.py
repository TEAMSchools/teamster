from dagster import ScheduleDefinition

from teamster.kipptaf import LOCAL_TIMEZONE
from teamster.kipptaf.fivetran.jobs import (
    fivetran_start_resync_jobs,
    kipptaf_fivetran_adp_workforce_now_start_sync_job,
    kipptaf_fivetran_illuminate_start_sync_job,
    kipptaf_fivetran_start_syncs_job,
)

adp_wfn_resync_schedule = ScheduleDefinition(
    cron_schedule="0 20 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=[
        job
        for job in fivetran_start_resync_jobs
        if job.name == "kipptaf_adp_workforce_now_fivetran_start_resync_job"
    ][0],
)

kipptaf_fivetran_start_syncs_schedule = ScheduleDefinition(
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=kipptaf_fivetran_start_syncs_job,
)

kipptaf_fivetran_adp_workforce_now_start_sync_schedule = ScheduleDefinition(
    cron_schedule="0 0-19 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=kipptaf_fivetran_adp_workforce_now_start_sync_job,
)

kipptaf_fivetran_illuminate_start_sync_schedule = ScheduleDefinition(
    cron_schedule="5 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=kipptaf_fivetran_illuminate_start_sync_job,
)

__all__ = [
    adp_wfn_resync_schedule,
    kipptaf_fivetran_adp_workforce_now_start_sync_schedule,
    kipptaf_fivetran_illuminate_start_sync_schedule,
    kipptaf_fivetran_start_syncs_schedule,
]
