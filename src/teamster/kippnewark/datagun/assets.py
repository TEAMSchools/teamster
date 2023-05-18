from teamster.core.datagun.assets import generate_extract_assets

from .. import CODE_LOCATION, LOCAL_TIMEZONE

powerschool_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="powerschool",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

__all__ = [
    *powerschool_extract_assets,
]
