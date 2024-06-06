from dagster import define_asset_job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.ldap.assets import assets

ldap_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_ldap_asset_job", selection=assets
)

jobs = [
    ldap_asset_job,
]
