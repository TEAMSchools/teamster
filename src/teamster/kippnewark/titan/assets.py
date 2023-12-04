from dagster import config_from_files

from teamster.core.titan.assets import build_titan_sftp_asset

from .. import CODE_LOCATION, CURRENT_FISCAL_YEAR, LOCAL_TIMEZONE

__all__ = [
    build_titan_sftp_asset(
        code_location=CODE_LOCATION,
        config=asset,
        current_fiscal_year=CURRENT_FISCAL_YEAR,
        timezone=LOCAL_TIMEZONE,
    )
    for asset in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/titan/config/assets.yaml"]
    )["assets"]
]
