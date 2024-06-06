from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.ldap.jobs import ldap_asset_job

ldap_asset_job_schedule = ScheduleDefinition(
    job=ldap_asset_job,
    cron_schedule="0 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    ldap_asset_job_schedule,
]
