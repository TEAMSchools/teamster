from dagster import ScheduleDefinition

from ... import LOCAL_TIMEZONE
from .jobs import adp_wfn_update_workers_job

adp_wfn_worker_fields_update_schedule = ScheduleDefinition(
    job=adp_wfn_update_workers_job,
    cron_schedule="30 3 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)
