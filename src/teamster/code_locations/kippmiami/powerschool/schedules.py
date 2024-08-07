from dagster import ScheduleDefinition, define_asset_job

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.powerschool.assets import (
    powerschool_table_assets_no_partition,
)

powerschool_sis_asset_no_partition_job_schedule = ScheduleDefinition(
    job=define_asset_job(
        name=f"{CODE_LOCATION}_powerschool_sis_assets_no_partition_job",
        selection=powerschool_table_assets_no_partition,
    ),
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    powerschool_sis_asset_no_partition_job_schedule,
]
