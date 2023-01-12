from teamster.core.datagun.assets import generate_extract_assets

cpn_extract_assets = generate_extract_assets(
    code_location="kippcamden", name="cpn", extract_type="sftp"
)

powerschool_extract_assets = generate_extract_assets(
    code_location="kippcamden", name="powerschool", extract_type="sftp"
)
