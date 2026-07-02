from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.extracts.jobs import (
    focus_extract_asset_job,
    powerschool_extract_asset_job,
)

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_asset_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

focus_extract_assets_schedule = ScheduleDefinition(
    job=focus_extract_asset_job,
    cron_schedule="0 5 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    powerschool_extract_assets_schedule,
    focus_extract_assets_schedule,
]
