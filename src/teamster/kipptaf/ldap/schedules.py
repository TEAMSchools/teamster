from dagster import ScheduleDefinition

from .. import LOCAL_TIMEZONE
from .jobs import ldap_asset_job

ldap_asset_job_schedule = ScheduleDefinition(
    job=ldap_asset_job,
    cron_schedule="0 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

_all = [
    ldap_asset_job_schedule,
]
