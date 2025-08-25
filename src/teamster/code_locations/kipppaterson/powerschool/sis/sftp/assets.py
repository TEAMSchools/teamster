import pathlib

from dagster import config_from_files

from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.code_locations.kipppaterson.powerschool.sis.sftp.schema import SCHEMAS
from teamster.libraries.sftp.assets import (
    build_sftp_file_asset,
)

config_dir = pathlib.Path(__file__).parent / "config"

assets = [
    build_sftp_file_asset(
        asset_key=[CODE_LOCATION, "powerschool", "sis", "sftp", a["asset_name"]],
        remote_dir_regex=r"/data-team/kipppaterson/powerschool",
        remote_file_regex=rf"{a['asset_name']}\.csv",
        ssh_resource_key="ssh_couchdrop",
        avro_schema=SCHEMAS[a["asset_name"]],
        slugify_replacements=[[f"{a['asset_name'].upper()}.", ""]],
    )
    for a in config_from_files([(f"{config_dir}/assets.yaml")])["assets"]
]
