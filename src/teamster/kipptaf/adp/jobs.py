from dagster import AssetSelection, define_asset_job

from .assets import wfm_assets_daily

daily_partition_asset_jobs = [
    define_asset_job(
        name="deanslist_static_partition_asset_job",
        selection=AssetSelection.assets(asset),
        partitions_def=asset.partitions_def,
    )
    for asset in wfm_assets_daily
]

__all__ = [
    *daily_partition_asset_jobs,
]
