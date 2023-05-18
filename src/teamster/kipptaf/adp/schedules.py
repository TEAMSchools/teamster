from dagster import build_schedule_from_partitioned_job

from teamster.core.adp.schedules import build_adp_wfm_schedule

from .. import CODE_LOCATION
from .assets import wfm_assets_dynamic
from .jobs import daily_partition_asset_job, dynamic_partition_asset_job

daily_partition_asset_job_schedule = build_schedule_from_partitioned_job(
    job=daily_partition_asset_job, hour_of_day=0, minute_of_hour=0
)

dynamic_partition_asset_job_schedule = build_adp_wfm_schedule(
    cron_schedule="0 0 * * *",
    code_location=CODE_LOCATION,
    source_system="adp",
    job=dynamic_partition_asset_job,
    asset_defs=wfm_assets_dynamic,
)

__all__ = [
    daily_partition_asset_job_schedule,
    dynamic_partition_asset_job_schedule,
]
