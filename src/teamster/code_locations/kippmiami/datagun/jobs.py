from dagster import define_asset_job

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.code_locations.kippmiami.datagun.assets import powerschool_extract_assets

powerschool_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_datagun_powerschool_extract_asset_job",
    selection=powerschool_extract_assets,
)
