from dagster import AssetSelection, define_asset_job

from .. import CODE_LOCATION
from . import assets

ldap_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_ldap_asset_job", selection=AssetSelection.assets(*assets)
)

__all__ = [
    ldap_asset_job,
]
