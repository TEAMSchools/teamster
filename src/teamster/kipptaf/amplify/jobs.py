from dagster import MAX_RUNTIME_SECONDS_TAG, AssetSelection, define_asset_job

from .assets import mclass_assets

mclass_asset_job = define_asset_job(
    name="mclass_asset_job",
    selection=AssetSelection.assets(*mclass_assets),
    partitions_def=mclass_assets[0].partitions_def,
    tags={MAX_RUNTIME_SECONDS_TAG: (60 * 15)},
)

_all = [
    mclass_asset_job,
]
