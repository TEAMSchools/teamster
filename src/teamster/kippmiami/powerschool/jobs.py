from dagster import MAX_RUNTIME_SECONDS_TAG, define_asset_job

from .assets import nonpartition_assets

powerschool_nonpartition_asset_job = define_asset_job(
    name="powerschool_nonpartition_asset_job",
    selection=nonpartition_assets,
    tags={MAX_RUNTIME_SECONDS_TAG: (60 * 3)},
)

_all = [
    powerschool_nonpartition_asset_job,
]
