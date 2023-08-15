from dagster import config_from_files

from teamster.core.pearson.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset

from .. import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/pearson/config"

sftp_assets = [
    build_sftp_asset(
        code_location=CODE_LOCATION,
        source_system="pearson",
        asset_fields=ASSET_FIELDS,
        ssh_resource_key="ssh_couchdrop",
        **a,
    )
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

__all__ = [
    *sftp_assets,
]
