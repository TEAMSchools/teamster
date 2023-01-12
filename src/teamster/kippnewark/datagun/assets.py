from teamster.core.datagun.assets import generate_extract_assets

nps_extract_assets = generate_extract_assets(
    code_location="kippnewark", name="nps", extract_type="sftp"
)

powerschool_extract_assets = generate_extract_assets(
    code_location="kippnewark", name="powerschool", extract_type="sftp"
)
