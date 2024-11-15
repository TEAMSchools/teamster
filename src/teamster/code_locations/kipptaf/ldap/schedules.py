from dagster import ScheduleDefinition, define_asset_job

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.ldap.assets import assets

ldap_asset_job_schedule = ScheduleDefinition(
    job=define_asset_job(name=f"{CODE_LOCATION}_ldap_asset_job", selection=assets),
    cron_schedule="15 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    ldap_asset_job_schedule,
]
