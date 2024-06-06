from dagster import define_asset_job

from teamster.code_locations.kippcamden.datagun.assets import powerschool_extract_assets

powerschool_extract_asset_job = define_asset_job(
    name="datagun_powerschool_extract_asset_job", selection=powerschool_extract_assets
)

jobs = [
    powerschool_extract_asset_job,
]
