import pathlib

from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.code_locations.kippmiami.fldoe.schema import ASSET_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_asset

assets = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "fldoe", a["asset_name"]],
        ssh_resource_key="ssh_couchdrop",
        avro_schema=ASSET_SCHEMA[a["asset_name"]],
        partitions_def=MultiPartitionsDefinition(
            {
                "school_year_term": StaticPartitionsDefinition(
                    a["partition_keys"]["school_year_term"]
                ),
                "grade_level_subject": StaticPartitionsDefinition(
                    a["partition_keys"]["grade_level_subject"]
                ),
            }
        ),
        **a,
    )
    for a in config_from_files(
        [f"{pathlib.Path(__file__).parent}/config/assets.yaml"],
    )["assets"]
]
