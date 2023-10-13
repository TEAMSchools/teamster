from dagster import (
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)
from teamster.core.clever.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.functions import get_avro_record_schema

from .. import CODE_LOCATION

__all__ = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "clever_reports", a["asset_name"]],
        ssh_resource_key="ssh_clever_reports",
        avro_schema=get_avro_record_schema(
            name=a["asset_name"], fields=ASSET_FIELDS[a["asset_name"]]
        ),
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
        [f"src/teamster/{CODE_LOCATION}/clever/config/assets.yaml"]
    )["assets"]
]
