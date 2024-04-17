from dagster import MAX_RUNTIME_SECONDS_TAG, define_asset_job

from .assets import _all

mclass_asset_job = define_asset_job(
    name="mclass_asset_job", selection=_all, tags={MAX_RUNTIME_SECONDS_TAG: (60 * 15)}
)

_all = [
    mclass_asset_job,
]
