import pathlib

from dagster import config_from_files

from teamster.core.sftp.assets import build_sftp_asset
from teamster.kipptaf.adp.workforce_now.sftp.schema import ASSET_SCHEMA

assets = [
    build_sftp_asset(
        asset_key=["adp", "workforce_now", a["asset_name"]],
        ssh_resource_key="ssh_adp_workforce_now",
        avro_schema=ASSET_SCHEMA[a["asset_name"]],
        **a,
    )
    for a in config_from_files([f"{pathlib.Path(__file__).parent}/config/assets.yaml"])[
        "assets"
    ]
]
