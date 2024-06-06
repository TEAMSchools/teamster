from dagster import define_asset_job

from teamster.code_locations.kippmiami.powerschool.assets import nonpartition_assets

powerschool_nonpartition_asset_job = define_asset_job(
    name="powerschool_nonpartition_asset_job", selection=nonpartition_assets
)

jobs = [
    powerschool_nonpartition_asset_job,
]
