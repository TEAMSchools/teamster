from dagster import ScheduleDefinition

from teamster.code_locations.kipppaterson import LOCAL_TIMEZONE
from teamster.code_locations.kipppaterson.extracts.jobs import (
    powerschool_extract_asset_job,
)

# 03:05 slot of the staggered 03:00 jobs (#6365). PowerSchool AutoComm must import
# this file no earlier than 03:30, so the run and one retry finish first.
powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_asset_job,
    cron_schedule="5 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    powerschool_extract_assets_schedule,
]
