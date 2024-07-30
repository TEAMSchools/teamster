from dagster import ScheduleDefinition, define_asset_job

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.powerschool.assets import (
    powerschool_table_assets_no_partition,
)

nonpartition_asset_job_schedule = ScheduleDefinition(
    job=define_asset_job(
        name=f"{CODE_LOCATION}_powerschool_nonpartition_asset_job",
        selection=powerschool_table_assets_no_partition,
    ),
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    nonpartition_asset_job_schedule,
]
