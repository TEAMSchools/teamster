from dagster import ScheduleDefinition

from .. import LOCAL_TIMEZONE
from .jobs import dbt_adp_wfm_asset_job

dbt_adp_wfm_asset_job_schedule = ScheduleDefinition(
    job=dbt_adp_wfm_asset_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

__all__ = [
    dbt_adp_wfm_asset_job_schedule,
]
