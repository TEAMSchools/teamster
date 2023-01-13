from dagster import AssetSelection, define_asset_job

from teamster.kippnewark.datagun.assets import (
    nps_extract_assets,
    powerschool_extract_assets,
)

nps_extract_assets_job = define_asset_job(
    name="nps_extract_assets_job",
    selection=AssetSelection.assets(*nps_extract_assets),
)

powerschool_extract_assets_job = define_asset_job(
    name="powerschool_extract_assets_job",
    selection=AssetSelection.assets(*powerschool_extract_assets),
)
