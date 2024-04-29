from dagster import ScheduleDefinition

from teamster.core.powerschool.schedules import build_powerschool_schedule

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import full_assets
from .jobs import powerschool_nonpartition_asset_job

last_modified_schedule = build_powerschool_schedule(
    code_location=CODE_LOCATION,
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    asset_defs=full_assets,
    max_runtime_seconds=(60 * 3),
)

nonpartition_asset_job_schedule = ScheduleDefinition(
    job=powerschool_nonpartition_asset_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

_all = [
    last_modified_schedule,
    nonpartition_asset_job_schedule,
]
