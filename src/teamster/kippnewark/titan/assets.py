from teamster.core.titan.assets import build_titan_sftp_assets

from .. import CODE_LOCATION, CURRENT_FISCAL_YEAR, LOCAL_TIMEZONE

sftp_assets = build_titan_sftp_assets(
    code_location=CODE_LOCATION,
    fiscal_year=CURRENT_FISCAL_YEAR,
    timezone=LOCAL_TIMEZONE,
)

__all__ = [
    *sftp_assets,
]
