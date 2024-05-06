from dagster import ScheduleDefinition, build_schedule_from_partitioned_job

from .... import LOCAL_TIMEZONE
from .jobs import adp_wfn_api_workers_asset_job, adp_wfn_update_workers_job

adp_wfn_worker_fields_update_schedule = ScheduleDefinition(
    job=adp_wfn_update_workers_job,
    cron_schedule="30 3 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

adp_wfn_api_workers_asset_schedule = build_schedule_from_partitioned_job(
    job=adp_wfn_api_workers_asset_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    adp_wfn_worker_fields_update_schedule,
    adp_wfn_api_workers_asset_schedule,
]
