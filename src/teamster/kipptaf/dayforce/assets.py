import pathlib

from dagster import config_from_files

from teamster.core.sftp.assets import build_sftp_asset
from teamster.kipptaf.dayforce.schema import ASSET_SCHEMA

assets = [
    build_sftp_asset(
        asset_key=["dayforce", a["asset_name"]],
        ssh_resource_key="ssh_couchdrop",
        remote_dir="/data-team/kipptaf/dayforce",
        avro_schema=ASSET_SCHEMA,
        **a,
    )
    for a in config_from_files(
        [f"{pathlib.Path(__file__).parent}/config/assets.yaml"],
    )["assets"]
]
