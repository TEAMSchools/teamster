from dagster import ScheduleDefinition

from teamster.code_locations.kippcamden import LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.extracts.jobs import (
    powerschool_extract_asset_job,
)

# 03:05 slot of the staggered 03:00 jobs (#6365). PowerSchool AutoComm imports
# this file at 03:30, so the run and one retry must finish before then.
powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_asset_job,
    cron_schedule="5 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    powerschool_extract_assets_schedule,
]
