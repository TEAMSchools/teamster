from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.powerschool.assets import (
    powerschool_table_assets_gradebook_full,
    powerschool_table_assets_gradebook_monthly,
    powerschool_table_assets_nightly,
    powerschool_table_assets_no_partition,
)
from teamster.libraries.powerschool.sis.odbc.schedules import (
    build_powerschool_sis_asset_schedule,
)

powerschool_sis_asset_gradebook_schedule = build_powerschool_sis_asset_schedule(
    code_location=CODE_LOCATION,
    asset_selection=[
        *powerschool_table_assets_gradebook_full,
        *powerschool_table_assets_gradebook_monthly,
    ],
    cron_schedule="0 2 * * *",
    execution_timezone=LOCAL_TIMEZONE,
)

powerschool_sis_asset_no_partition_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__powerschool__sis__assets_no_partition_job_schedule",
    target=[*powerschool_table_assets_nightly, *powerschool_table_assets_no_partition],
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    tags={MAX_RUNTIME_SECONDS_TAG: str(60 * 10)},
)

schedules = [
    powerschool_sis_asset_gradebook_schedule,
    powerschool_sis_asset_no_partition_job_schedule,
]
