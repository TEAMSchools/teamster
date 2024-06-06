from dagster import ScheduleDefinition

from teamster.kipptaf import LOCAL_TIMEZONE
from teamster.kipptaf.ldap.jobs import ldap_asset_job

ldap_asset_job_schedule = ScheduleDefinition(
    job=ldap_asset_job,
    cron_schedule="0 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    ldap_asset_job_schedule,
]
