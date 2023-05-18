from teamster.core.edplan.assets import build_edplan_sftp_asset

from .. import CODE_LOCATION, LOCAL_TIMEZONE

sftp_assets = build_edplan_sftp_asset(
    config_dir=f"src/teamster/{CODE_LOCATION}/edplan/config",
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
)


__all__ = [
    *sftp_assets,
]
