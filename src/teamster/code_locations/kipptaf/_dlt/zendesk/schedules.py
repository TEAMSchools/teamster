from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf._dlt.zendesk.assets import assets

zendesk_dlt_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__dlt__zendesk__asset_job",
    target=assets,
    cron_schedule="0 5 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    zendesk_dlt_asset_job_schedule,
]
