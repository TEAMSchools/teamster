from dagster import AssetSelection, define_asset_job

from .assets import powerschool_extract_assets

powerschool_extract_assets_job = define_asset_job(
    name="powerschool_extract_assets_job",
    selection=AssetSelection.assets(*powerschool_extract_assets),
)

__all__ = [powerschool_extract_assets_job]
