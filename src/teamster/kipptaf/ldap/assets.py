import pathlib

from dagster import config_from_files

from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.ldap.schema import ASSET_SCHEMA
from teamster.ldap.assets import build_ldap_asset

ldap_assets = [
    build_ldap_asset(**asset)
    for asset in config_from_files(
        [f"{pathlib.Path(__file__).parent}/config/assets.yaml"]
    )["assets"]
]

assets = [
    *ldap_assets,
]
