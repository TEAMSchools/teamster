from dagster import (
    AutoMaterializePolicy,
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.clever.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset

from .. import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/clever/config"

sftp_assets = [
    build_sftp_asset(
        code_location=CODE_LOCATION,
        source_system="clever_reports",
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "date": DynamicPartitionsDefinition(
                    name=f"{CODE_LOCATION}__clever_reports__{a['asset_name']}_date"
                ),
                "type": StaticPartitionsDefinition(["staff", "students", "teachers"]),
            }
        ),
        auto_materialize_policy=AutoMaterializePolicy.eager(),
        **a,
    )
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

__all__ = [
    *sftp_assets,
]
