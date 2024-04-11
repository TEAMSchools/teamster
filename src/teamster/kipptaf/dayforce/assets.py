import pathlib

from dagster import config_from_files

from teamster.core.sftp.assets import build_sftp_asset

from .. import CODE_LOCATION
from .schema import ASSET_SCHEMA

_all = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "dayforce", a["asset_name"]],
        ssh_resource_key="ssh_couchdrop",
        avro_schema=ASSET_SCHEMA,
        **a,
    )
    for a in config_from_files(
        [f"{pathlib.Path(__file__).parent}/config/assets.yaml"],
    )["assets"]
]
