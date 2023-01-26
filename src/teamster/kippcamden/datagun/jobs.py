from dagster import AssetSelection, define_asset_job

from teamster.kippcamden.datagun.assets import (
    cpn_extract_assets,
    powerschool_extract_assets,
)

cpn_extract_assets_job = define_asset_job(
    name="cpn_extract_assets_job",
    selection=AssetSelection.assets(*cpn_extract_assets),
)

powerschool_extract_assets_job = define_asset_job(
    name="powerschool_extract_assets_job",
    selection=AssetSelection.assets(*powerschool_extract_assets),
)

__all__ = [cpn_extract_assets_job, powerschool_extract_assets_job]
