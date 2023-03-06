from dagster import AssetSelection, define_asset_job

from teamster.kippcamden.powerschool.db.assets import nonpartition_assets

powerschool_nonpartition_assets_job = define_asset_job(
    name="powerschool_nonpartition_assets_job",
    selection=AssetSelection.assets(*nonpartition_assets),
)

__all__ = [powerschool_nonpartition_assets_job]
