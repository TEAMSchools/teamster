from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition

from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.overgrad.assets import assets

overgrad_asset_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__overgrad__asset_schedule",
    target=assets,
    cron_schedule=["0 1 * * *", "0 15 * * *"],
    execution_timezone=str(LOCAL_TIMEZONE),
    tags={MAX_RUNTIME_SECONDS_TAG: str(3600)},
)

schedules = [
    overgrad_asset_schedule,
]
