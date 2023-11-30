from dagster import AssetSelection, define_asset_job

from ... import CODE_LOCATION
from .assets import adp_wfm_assets_daily, adp_wfm_assets_dynamic

adp_wfm_daily_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_adp_wfm_daily_partition_asset_job",
    selection=AssetSelection.assets(*adp_wfm_assets_daily),
    partitions_def=adp_wfm_assets_daily[0].partitions_def,
)

adp_wfm_dynamic_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_adp_wfm_dynamic_partition_asset_job",
    selection=AssetSelection.assets(*adp_wfm_assets_dynamic),
    partitions_def=adp_wfm_assets_dynamic[0].partitions_def,
)
