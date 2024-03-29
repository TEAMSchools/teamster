from dagster import define_asset_job

from .. import CODE_LOCATION
from . import assets

ldap_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_ldap_asset_job", selection=assets
)

_all = [
    ldap_asset_job,
]
