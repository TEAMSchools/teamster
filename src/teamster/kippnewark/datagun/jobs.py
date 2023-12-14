from dagster import AssetSelection, define_asset_job

from .assets import powerschool_extract_assets

powerschool_extract_asset_job = define_asset_job(
    name="datagun_powerschool_extract_asset_job",
    selection=AssetSelection.assets(*powerschool_extract_assets),
)

_all = [
    powerschool_extract_asset_job,
]
