from dagster import AssetSelection, define_asset_job

from . import assets

powerschool_nonpartition_asset_job = define_asset_job(
    name="powerschool_nonpartition_asset_job",
    selection=AssetSelection.assets(*assets.nonpartition_assets),
)

__all__ = [powerschool_nonpartition_asset_job]
