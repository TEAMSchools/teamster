import yaml

from teamster.core.datagun.assets import (
    gsheet_extract_asset_factory,
    sftp_extract_asset_factory,
)

sftp_extract_assets = []
with open("src/teamster/kipptaf/datagun/config/assets_sftp.yaml") as f:
    sftp_extract_configs = yaml.safe_load(f)

for sec in sftp_extract_configs:
    sftp_extract_assets.append(sftp_extract_asset_factory(**sec))

gsheet_extract_assets = []
with open("src/teamster/kipptaf/datagun/config/assets_gsheet.yaml") as f:
    gsheet_extract_configs = yaml.safe_load(f)

for gec in gsheet_extract_configs:
    gsheet_extract_assets.append(gsheet_extract_asset_factory(**gec))
