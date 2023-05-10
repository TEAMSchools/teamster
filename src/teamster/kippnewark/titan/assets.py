from teamster.core.titan.assets import build_titan_sftp_assets

from .. import CODE_LOCATION

sftp_assets = build_titan_sftp_assets(
    config_dir=f"src/teamster/{CODE_LOCATION}/titan/config", code_location=CODE_LOCATION
)

__all__ = [
    *sftp_assets,
]
