from dagster import AssetSelection, define_asset_job

from teamster.kippmiami.powerschool.db.assets import nonpartition_assets

nonpartition_assets_job = define_asset_job(
    name="nonpartition_assets_job",
    selection=AssetSelection.assets(*nonpartition_assets),
)

__all__ = [nonpartition_assets_job]
