from dagster import define_asset_job

from .assets import _all

mclass_asset_job = define_asset_job(name="mclass_asset_job", selection=_all)

_all = [
    mclass_asset_job,
]
