from dagster import AssetSelection, define_asset_job, job

from .assets import wfm_assets_daily, wfm_assets_dynamic
from .ops import adp_wfn_get_worker_update_data_op, adp_wfn_update_workers_op

daily_partition_asset_job = define_asset_job(
    name="kipptaf_adp_wfm_daily_partition_asset_job",
    selection=AssetSelection.assets(*wfm_assets_daily),
    partitions_def=wfm_assets_daily[0].partitions_def,
)

dynamic_partition_asset_job = define_asset_job(
    name="kipptaf_adp_wfm_dynamic_partition_asset_job",
    selection=AssetSelection.assets(*wfm_assets_dynamic),
    partitions_def=wfm_assets_dynamic[0].partitions_def,
)


@job
def adp_wfn_update_workers_job():
    worker_data = adp_wfn_get_worker_update_data_op()

    adp_wfn_update_workers_op(worker_data)


__all__ = [
    daily_partition_asset_job,
    dynamic_partition_asset_job,
    adp_wfn_update_workers_job,
]
