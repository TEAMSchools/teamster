import pathlib

from dagster import (
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.sftp.assets import build_sftp_asset

from .. import CODE_LOCATION
from .schema import ASSET_FIELDS

_all = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "clever_reports", a["asset_name"]],
        ssh_resource_key="ssh_clever_reports",
        avro_schema=ASSET_FIELDS[a["asset_name"]],
        partitions_def=MultiPartitionsDefinition(
            {
                "date": DynamicPartitionsDefinition(
                    name=f"{CODE_LOCATION}__clever_reports__{a['asset_name']}_date"
                ),
                "type": StaticPartitionsDefinition(["staff", "students", "teachers"]),
            }
        ),
        **a,
    )
    for a in config_from_files(
        [f"{pathlib.Path(__file__).parent}/config/assets.yaml"],
    )["assets"]
]
