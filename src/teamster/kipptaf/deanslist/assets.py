import pathlib

from dagster import config_from_files

from teamster.core.sftp.assets import build_sftp_asset
from teamster.deanslist.schema import ...
from teamster.kipptaf import CODE_LOCATION

assets = [
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