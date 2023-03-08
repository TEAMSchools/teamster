from teamster.core.datagun.assets import generate_extract_assets

from .. import CODE_LOCATION

nps_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="nps", extract_type="sftp"
)

powerschool_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="powerschool", extract_type="sftp"
)
