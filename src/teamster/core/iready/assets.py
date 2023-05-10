from dagster import (
    AutoMaterializePolicy,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.iready.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.core.utils.variables import LOCAL_TIME_ZONE


def build_iready_sftp_asset(config_dir, code_location):
    sftp_assets = []

    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]:
        asset = build_sftp_asset(
            code_location=code_location,
            source_system="iready",
            asset_fields=ASSET_FIELDS,
            partitions_def=MultiPartitionsDefinition(
                {
                    "subject": StaticPartitionsDefinition(["ela", "math"]),
                    "date": FiscalYearPartitionsDefinition(
                        start_date=a["partition_start_date"],
                        timezone=LOCAL_TIME_ZONE.name,
                        start_month=7,
                        fmt="%Y-%m-%d",
                    ),
                }
            ),
            auto_materialize_policy=AutoMaterializePolicy.eager(),
            **a,
        )

        sftp_assets.append(asset)

    return sftp_assets
