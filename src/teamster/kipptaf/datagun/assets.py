from dagster import config_from_files

from teamster.core.datagun.assets import (
    gsheet_extract_asset_factory,
    sftp_extract_asset_factory,
)

sftp_extract_config = config_from_files(
    ["src/teamster/kipptaf/datagun/config/assets/sftp.yaml"]
)
sftp_extract_assets = []
for sec in sftp_extract_config["assets"]:
    sftp_extract_assets.append(sftp_extract_asset_factory(**sec))

gsheet_extract_config = config_from_files(
    ["src/teamster/kipptaf/datagun/config/assets/gsheets.yaml"]
)
gsheet_extract_assets = []
for gec in gsheet_extract_config["assets"]:
    gsheet_extract_assets.append(gsheet_extract_asset_factory(**gec))
