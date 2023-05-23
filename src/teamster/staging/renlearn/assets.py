from teamster.core.renlearn.assets import build_renlearn_sftp_asset

from .. import CODE_LOCATION, LOCAL_TIMEZONE

sftp_assets = build_renlearn_sftp_asset(
    config_dir=f"src/teamster/{CODE_LOCATION}/renlearn/config",
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
)

__all__ = [
    *sftp_assets,
]
