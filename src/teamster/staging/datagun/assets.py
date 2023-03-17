from teamster.core.datagun.assets import generate_extract_assets

sftp_extract_assets = generate_extract_assets(
    code_location="staging", name="sftp", extract_type="sftp"
)

gsheet_extract_assets = generate_extract_assets(
    code_location="staging", name="gsheet", extract_type="gsheet"
)

__all__ = [
    *sftp_extract_assets,
    *gsheet_extract_assets,
]
