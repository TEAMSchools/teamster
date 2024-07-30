from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition, define_asset_job

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.powerschool.assets import (
    full_assets,
    nonpartition_assets,
)
from teamster.libraries.powerschool.sis.schedules import build_powerschool_schedule

last_modified_schedule = build_powerschool_schedule(
    code_location=CODE_LOCATION,
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    asset_defs=full_assets,
    max_runtime_seconds=(60 * 5),
)

nonpartition_asset_job_schedule = ScheduleDefinition(
    job=define_asset_job(
        name=f"{CODE_LOCATION}_powerschool_nonpartition_asset_job",
        selection=nonpartition_assets,
    ),
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    tags={MAX_RUNTIME_SECONDS_TAG: str(60 * 10)},
)

schedules = [
    last_modified_schedule,
    nonpartition_asset_job_schedule,
]
