from dagster import DynamicPartitionsDefinition, config_from_files

from teamster.core.achieve3k.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset

from .. import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/achieve3k/config"

sftp_assets = [
    build_sftp_asset(
        code_location=CODE_LOCATION,
        source_system="achieve3k",
        asset_fields=ASSET_FIELDS,
        partitions_def=DynamicPartitionsDefinition(
            name=f"{CODE_LOCATION}__achieve3k__{a['asset_name']}"
        ),
        **a,
    )
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

__all__ = [
    *sftp_assets,
]
