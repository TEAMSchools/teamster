from dagster import build_schedule_from_partitioned_job

from teamster.core.adp.schedules import build_adp_wfm_schedule

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import wfm_assets_dynamic
from .jobs import daily_partition_asset_job, dynamic_partition_asset_job

daily_partition_asset_job_schedule = build_schedule_from_partitioned_job(
    job=daily_partition_asset_job, hour_of_day=23, minute_of_hour=50
)

dynamic_partition_asset_job_schedule = build_adp_wfm_schedule(
    cron_schedule="50 23 * * *",
    code_location=CODE_LOCATION,
    source_system="adp",
    execution_timezone=LOCAL_TIMEZONE,
    job=dynamic_partition_asset_job,
    asset_defs=wfm_assets_dynamic,
)

__all__ = [
    daily_partition_asset_job_schedule,
    dynamic_partition_asset_job_schedule,
]
