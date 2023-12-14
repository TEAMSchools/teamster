from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.iready.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.functions import get_avro_record_schema

from .. import CODE_LOCATION

_all = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "iready", a["asset_name"]],
        ssh_resource_key="ssh_iready",
        avro_schema=get_avro_record_schema(
            name=a["asset_name"], fields=ASSET_FIELDS[a["asset_name"]]
        ),
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["ela", "math"]),
                "academic_year": StaticPartitionsDefinition(
                    a["partition_keys"]["academic_year"]
                ),
            }
        ),
        slugify_replacements=[["%", "percent"]],
        **a,
    )
    for a in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/iready/config/assets.yaml"]
    )["assets"]
]
