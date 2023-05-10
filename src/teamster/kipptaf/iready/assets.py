from teamster.core.iready.assets import build_iready_sftp_asset

from .. import CODE_LOCATION

sftp_assets = build_iready_sftp_asset(
    config_dir=f"src/teamster/{CODE_LOCATION}/iready/config",
    code_location=CODE_LOCATION,
)

__all__ = [
    *sftp_assets,
]
