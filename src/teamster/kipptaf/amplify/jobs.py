from dagster import AssetSelection, define_asset_job

from .assets import mclass_assets

mclass_asset_job = define_asset_job(
    name="mclass_asset_job",
    selection=AssetSelection.assets(*mclass_assets),
    partitions_def=mclass_assets[0].partitions_def,
)

__all__ = [
    mclass_asset_job,
]
