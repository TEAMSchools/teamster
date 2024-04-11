import pathlib

from dagster import config_from_files

from teamster.core.deanslist.schema import ASSET_SCHEMA
from teamster.core.sftp.assets import build_sftp_asset

from .. import CODE_LOCATION

_all = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "deanslist", a["asset_name"]],
        ssh_resource_key="ssh_deanslist",
        avro_schema=ASSET_SCHEMA[a["asset_name"]],
        **a,
    )
    for a in config_from_files(
        [f"{pathlib.Path(__file__).parent}/config/assets.yaml"],
    )["assets"]
]
