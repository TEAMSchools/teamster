from dagster import config_from_files

from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.titan.schema import ASSET_FIELDS
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.core.utils.variables import LOCAL_TIME_ZONE

from .. import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/titan/config"

sftp_assets = []
for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]:
    partitions_def = FiscalYearPartitionsDefinition(
        start_date=a["partition_start_date"],
        timezone=LOCAL_TIME_ZONE.name,
        start_month=7,
        fmt="%Y-%m-%d",
    )

    asset = build_sftp_asset(
        code_location=CODE_LOCATION,
        source_system="titan",
        asset_fields=ASSET_FIELDS,
        partitions_def=partitions_def,
        **a,
    )

    sftp_assets.append(asset)

__all__ = [
    *sftp_assets,
]
