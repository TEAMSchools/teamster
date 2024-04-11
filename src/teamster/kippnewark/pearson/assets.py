import pathlib

from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.pearson.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset

from .. import CODE_LOCATION

config_dir = pathlib.Path(__file__).parent / "config"

njgpa = build_sftp_asset(
    asset_key=[CODE_LOCATION, "pearson", "njgpa"],
    remote_dir="/teamster-kippnewark/couchdrop/pearson/njgpa",
    remote_file_regex="pc(?P<administration>\w+)(?P<fiscal_year>\d+)_NJ-\d+_\w+GPA\w+\.csv",
    avro_schema=ASSET_FIELDS["njgpa"],
    ssh_resource_key="ssh_couchdrop",
    partitions_def=MultiPartitionsDefinition(
        {
            "fiscal_year": StaticPartitionsDefinition(["22", "23"]),
            "administration": StaticPartitionsDefinition(["spr", "fbk"]),
        }
    ),
)

all_assets = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "pearson", a["asset_name"]],
        avro_schema=ASSET_FIELDS[a["asset_name"]],
        ssh_resource_key="ssh_couchdrop",
        partitions_def=StaticPartitionsDefinition(a["partition_keys"]),
        **a,
    )
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

_all = [
    njgpa,
    *all_assets,
]
