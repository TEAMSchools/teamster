from teamster.core.datagun.assets import generate_extract_assets

powerschool_extract_assets = generate_extract_assets(
    code_location="kippmiami", name="powerschool", extract_type="sftp"
)
