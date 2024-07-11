import pathlib

from dagster import config_from_files

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.dayforce.schema import ASSET_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_file_asset

assets = [
    build_sftp_file_asset(
        asset_key=[CODE_LOCATION, "dayforce", a["asset_name"]],
        ssh_resource_key="ssh_couchdrop",
        remote_dir_regex=r"/data-team/kipptaf/dayforce",
        avro_schema=ASSET_SCHEMA,
        **a,
    )
    for a in config_from_files(
        [f"{pathlib.Path(__file__).parent}/config/assets.yaml"],
    )["assets"]
]
