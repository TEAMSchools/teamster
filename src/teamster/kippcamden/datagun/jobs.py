from dagster import AssetSelection, define_asset_job

from . import assets

cpn_extract_asset_job = define_asset_job(
    name="datagun_cpn_extract_asset_job",
    selection=AssetSelection.assets(*assets.cpn_extract_assets),
)

powerschool_extract_asset_job = define_asset_job(
    name="datagun_powerschool_extract_asset_job",
    selection=AssetSelection.assets(*assets.powerschool_extract_assets),
)

__all__ = [
    cpn_extract_asset_job,
    powerschool_extract_asset_job,
]
