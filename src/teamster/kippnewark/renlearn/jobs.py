from dagster import define_asset_job

from .. import CODE_LOCATION
from . import assets

asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__renlearn__asset_job", selection=assets
)

__all__ = [
    asset_job,
]
