from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition, define_asset_job

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.powerschool.assets import (
    powerschool_table_assets_gradebook_full,
    powerschool_table_assets_gradebook_monthly,
    powerschool_table_assets_no_partition,
)
from teamster.libraries.powerschool.sis.schedules import (
    build_powerschool_sis_asset_schedule,
)

powerschool_sis_asset_gradebook_schedule = build_powerschool_sis_asset_schedule(
    code_location=CODE_LOCATION,
    asset_selection=[
        *powerschool_table_assets_gradebook_full,
        *powerschool_table_assets_gradebook_monthly,
    ],
    cron_schedule="5 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

powerschool_sis_asset_no_partition_job_schedule = ScheduleDefinition(
    job=define_asset_job(
        name=f"{CODE_LOCATION}_powerschool_sis_assets_no_partition_job",
        selection=powerschool_table_assets_no_partition,
    ),
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    tags={MAX_RUNTIME_SECONDS_TAG: str(60 * 10)},
)

schedules = [
    powerschool_sis_asset_gradebook_schedule,
    powerschool_sis_asset_no_partition_job_schedule,
]
