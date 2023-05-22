from dagster import AssetSelection, define_asset_job

from .assets import wfm_assets_daily, wfm_assets_dynamic

daily_partition_asset_job = define_asset_job(
    name="staging_adp_wfm_daily_partition_asset_job",
    selection=AssetSelection.assets(*wfm_assets_daily),
    partitions_def=wfm_assets_daily[0].partitions_def,
)

dynamic_partition_asset_job = define_asset_job(
    name="staging_adp_wfm_dynamic_partition_asset_job",
    selection=AssetSelection.assets(*wfm_assets_dynamic),
    partitions_def=wfm_assets_dynamic[0].partitions_def,
)

__all__ = [
    daily_partition_asset_job,
    dynamic_partition_asset_job,
]
