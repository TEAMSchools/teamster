from teamster.core.datagun.assets import generate_extract_assets

from .. import CODE_LOCATION, LOCAL_TIMEZONE

sftp_extract_assets = generate_extract_assets(
    code_location="staging", name="sftp", extract_type="sftp", timezone=LOCAL_TIMEZONE
)

gsheet_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="gsheets",
    extract_type="gsheet",
    timezone=LOCAL_TIMEZONE,
)

__all__ = [
    *sftp_extract_assets,
    *gsheet_extract_assets,
]
