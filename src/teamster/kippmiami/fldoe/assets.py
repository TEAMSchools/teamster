from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.fldoe.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset

from .. import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/fldoe/config"

__all__ = [
    build_sftp_asset(
        code_location=CODE_LOCATION,
        source_system="fldoe",
        asset_fields=ASSET_FIELDS,
        ssh_resource_key="ssh_couchdrop",
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
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]
