from dagster import ResourceParam, config_from_files
from dagster_ssh import SSHResource

from teamster.core.renlearn.assets import build_sftp_asset

from .. import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/config/assets/renlearn"

sftp_assets = [
    build_sftp_asset(
        sftp_renlearn=ResourceParam[SSHResource],
        code_location=CODE_LOCATION,
        source_system="renlearn",
        **a,
    )
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

__all__ = [
    *sftp_assets,
]
