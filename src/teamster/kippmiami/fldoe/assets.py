from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.functions import get_avro_record_schema

from .. import CODE_LOCATION
from .schema import ASSET_FIELDS

__all__ = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "fldoe", a["asset_name"]],
        ssh_resource_key="ssh_couchdrop",
        avro_schema=get_avro_record_schema(
            name=a["asset_name"], fields=ASSET_FIELDS[a["asset_name"]]
        ),
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
        [f"src/teamster/{CODE_LOCATION}/fldoe/config/assets.yaml"]
    )["assets"]
]
