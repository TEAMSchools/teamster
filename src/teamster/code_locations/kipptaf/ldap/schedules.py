from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition, define_asset_job

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.ldap.assets import assets

ldap_asset_job_schedule = ScheduleDefinition(
    job=define_asset_job(name=f"{CODE_LOCATION}_ldap_asset_job", selection=assets),
    cron_schedule="45 5 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    tags={MAX_RUNTIME_SECONDS_TAG: str(60 * 5)},
)

schedules = [
    ldap_asset_job_schedule,
]
