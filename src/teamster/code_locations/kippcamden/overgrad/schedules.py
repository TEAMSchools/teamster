from dagster import ScheduleDefinition

from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.overgrad.assets import (
    admissions,
    custom_fields,
    followings,
    schools,
    students,
)

overgrad_asset_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__overgrad__asset_schedule",
    target=[admissions, custom_fields, followings, schools, students],
    cron_schedule=["0 1 * * *", "0 15 * * *"],
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    overgrad_asset_schedule,
]
