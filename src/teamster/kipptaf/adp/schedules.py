from dagster import ScheduleDefinition, build_schedule_from_partitioned_job

from teamster.core.adp.schedules import build_dynamic_partition_schedule

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import wfm_assets_dynamic
from .jobs import (
    adp_wfn_worker_fields_update_job,
    daily_partition_asset_job,
    dynamic_partition_asset_job,
)

adp_wfn_worker_fields_update_schedule = ScheduleDefinition(
    job=adp_wfn_worker_fields_update_job,
    cron_schedule="10 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

daily_partition_asset_job_schedule = build_schedule_from_partitioned_job(
    job=daily_partition_asset_job, hour_of_day=23, minute_of_hour=50
)

dynamic_partition_asset_job_schedule = build_dynamic_partition_schedule(
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
