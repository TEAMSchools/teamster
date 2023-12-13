from dagster import AssetSelection, define_asset_job

from .assets import nonpartition_assets

powerschool_nonpartition_asset_job = define_asset_job(
    name="powerschool_nonpartition_asset_job",
    selection=AssetSelection.assets(*nonpartition_assets),
)

_all = [
    powerschool_nonpartition_asset_job,
]
