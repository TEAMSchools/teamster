from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.ldap.assets import assets

ldap_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__ldap__assets_schedule",
    target=assets,
    cron_schedule="30 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    ldap_asset_job_schedule,
]
