from dagster import build_schedule_from_partitioned_job

from teamster.core.adp.workforce_manager.schedules import (
    build_dynamic_partition_schedule,
)

from ... import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import adp_wfm_assets_dynamic
from .jobs import adp_wfm_daily_partition_asset_job, adp_wfm_dynamic_partition_asset_job

adp_wfm_daily_partition_asset_job_schedule = build_schedule_from_partitioned_job(
    job=adp_wfm_daily_partition_asset_job, hour_of_day=23, minute_of_hour=50
)

adp_wfm_dynamic_partition_asset_job_schedule = build_dynamic_partition_schedule(
    cron_schedule="50 23 * * *",
    code_location=CODE_LOCATION,
    execution_timezone=LOCAL_TIMEZONE,
    job=adp_wfm_dynamic_partition_asset_job,
    asset_defs=adp_wfm_assets_dynamic,
)
