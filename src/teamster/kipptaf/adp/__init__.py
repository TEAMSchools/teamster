from .workforce_manager.assets import adp_wfm_assets_daily, adp_wfm_assets_dynamic
from .workforce_manager.jobs import (
    adp_wfm_daily_partition_asset_job,
    adp_wfm_dynamic_partition_asset_job,
)
from .workforce_manager.schedules import (
    adp_wfm_daily_partition_asset_job_schedule,
    adp_wfm_dynamic_partition_asset_job_schedule,
)
from .workforce_now.assets import adp_wfn_sftp_assets
from .workforce_now.jobs import adp_wfn_update_workers_job
from .workforce_now.ops import adp_wfn_update_workers_op
from .workforce_now.schedules import adp_wfn_worker_fields_update_schedule
from .workforce_now.sensors import adp_wfn_sftp_sensor

assets = [
    adp_wfm_assets_daily,
    adp_wfm_assets_dynamic,
    adp_wfn_sftp_assets,
]

jobs = [
    adp_wfm_daily_partition_asset_job,
    adp_wfm_dynamic_partition_asset_job,
    adp_wfn_update_workers_job,
]

schedules = [
    adp_wfm_daily_partition_asset_job_schedule,
    adp_wfm_dynamic_partition_asset_job_schedule,
    adp_wfn_worker_fields_update_schedule,
]

ops = [
    adp_wfn_update_workers_op,
]

sensors = [
    adp_wfn_sftp_sensor,
]

__all__ = [
    assets,
    jobs,
    ops,
    schedules,
    sensors,
]
