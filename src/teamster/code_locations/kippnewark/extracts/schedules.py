from dagster import ScheduleDefinition

from teamster.code_locations.kippnewark import LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.extracts.jobs import (
    powerschool_extract_asset_job,
)

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_asset_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    powerschool_extract_assets_schedule,
]
