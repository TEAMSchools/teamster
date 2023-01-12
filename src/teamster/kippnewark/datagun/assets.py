import yaml

from teamster.core.datagun.assets import sftp_extract_asset_factory

sftp_extract_assets = []
with open("src/teamster/kippnewark/datagun/config/assets_sftp.yaml") as f:
    sftp_extract_configs = yaml.safe_load(f)

for sec in sftp_extract_configs:
    sftp_extract_assets.append(sftp_extract_asset_factory(**sec))
