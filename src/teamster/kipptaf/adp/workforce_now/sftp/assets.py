import pathlib

from dagster import config_from_files

from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.functions import get_avro_record_schema

from .... import CODE_LOCATION
from .schema import ASSET_FIELDS

_all = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "adp", "workforce_now", a["asset_name"]],
        ssh_resource_key="ssh_adp_workforce_now",
        avro_schema=get_avro_record_schema(
            name=a["asset_name"], fields=ASSET_FIELDS[a["asset_name"]]
        ),
        **a,
    )
    for a in config_from_files([f"{pathlib.Path(__file__).parent}/config/assets.yaml"])[
        "assets"
    ]
]
