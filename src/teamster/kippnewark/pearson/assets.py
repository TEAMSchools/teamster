import pathlib

from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.pearson.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.functions import get_avro_record_schema

from .. import CODE_LOCATION

config_dir = pathlib.Path(__file__).parent / "config"

njgpa_assets = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "pearson", a["asset_name"]],
        avro_schema=get_avro_record_schema(
            name=a["asset_name"], fields=ASSET_FIELDS[a["asset_name"]]
        ),
        ssh_resource_key="ssh_couchdrop",
        partitions_def=MultiPartitionsDefinition(
            {k: StaticPartitionsDefinition(v) for k, v in a["partition_keys"].items()}
        ),
        **a,
    )
    for a in config_from_files([f"{config_dir}/njgpa.yaml"])["assets"]
]

all_assets = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "pearson", a["asset_name"]],
        avro_schema=get_avro_record_schema(
            name=a["asset_name"], fields=ASSET_FIELDS[a["asset_name"]]
        ),
        ssh_resource_key="ssh_couchdrop",
        partitions_def=StaticPartitionsDefinition(a["partition_keys"]),
        **a,
    )
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

_all = [
    *all_assets,
    *njgpa_assets,
]
