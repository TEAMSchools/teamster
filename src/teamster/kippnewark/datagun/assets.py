from dagster import config_from_files

from teamster.core.datagun.assets import sftp_extract_asset_factory

sftp_extract_config = config_from_files(
    ["src/teamster/kippnewark/datagun/config/assets/sftp.yaml"]
)
sftp_extract_assets = []
for sec in sftp_extract_config["assets"]:
    sftp_extract_assets.append(sftp_extract_asset_factory(**sec))
