from teamster.core.pearson.assets import build_pearson_sftp_assets

from .. import CODE_LOCATION, CURRENT_FISCAL_YEAR, LOCAL_TIMEZONE

sftp_assets = build_pearson_sftp_assets(
    config_dir=f"src/teamster/{CODE_LOCATION}/pearson/config",
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    max_fiscal_year=CURRENT_FISCAL_YEAR.fiscal_year - 1,
)

__all__ = [
    *sftp_assets,
]
