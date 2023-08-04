from dagster import config_from_files

from teamster.core.ldap.assets import build_ldap_asset

from .. import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/ldap/config"

ldap_assets = [
    build_ldap_asset(code_location=CODE_LOCATION, **asset)
    for asset in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

__all__ = [
    *ldap_assets,
]
