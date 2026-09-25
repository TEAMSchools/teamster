from dagster import DefaultScheduleStatus, ScheduleDefinition

from teamster.code_locations.kippnewark import LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.extracts.jobs import (
    parentsquare_extract_asset_job,
    powerschool_extract_asset_job,
)

# Ships STOPPED: no SFTP round-trip has been attempted and the upload path is
# unconfirmed. Un-pause once a one-file round-trip is verified with Ops.
parentsquare_extract_assets_schedule = ScheduleDefinition(
    job=parentsquare_extract_asset_job,
    cron_schedule="0 18 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    default_status=DefaultScheduleStatus.STOPPED,
)

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_asset_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    parentsquare_extract_assets_schedule,
    powerschool_extract_assets_schedule,
]
