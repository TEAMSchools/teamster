from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition

from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.powerschool.assets import full_assets
from teamster.code_locations.kippcamden.powerschool.jobs import (
    powerschool_nonpartition_asset_job,
)
from teamster.libraries.powerschool.sis.schedules import build_powerschool_schedule

powerschool_schedule = build_powerschool_schedule(
    code_location=CODE_LOCATION,
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    asset_defs=full_assets,
    max_runtime_seconds=(60 * 6),
)

nonpartition_asset_job_schedule = ScheduleDefinition(
    job=powerschool_nonpartition_asset_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    tags={MAX_RUNTIME_SECONDS_TAG: str(60 * 6)},
)

schedules = [
    powerschool_schedule,
    nonpartition_asset_job_schedule,
]
