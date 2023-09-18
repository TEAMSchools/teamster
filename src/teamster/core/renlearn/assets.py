from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.renlearn.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.classes import FiscalYearPartitionsDefinition


def build_renlearn_sftp_asset(config_dir, code_location, timezone):
    sftp_assets = []

    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]:
        asset = build_sftp_asset(
            code_location=code_location,
            source_system="renlearn",
            asset_fields=ASSET_FIELDS,
            partitions_def=MultiPartitionsDefinition(
                {
                    "start_date": FiscalYearPartitionsDefinition(
                        start_date=a["partition_keys"]["start_date"],
                        timezone=timezone.name,
                        start_month=7,
                    ),
                    "subject": StaticPartitionsDefinition(
                        a["partition_keys"]["subject"]
                    ),
                }
            ),
            slugify_cols=False,
            **a,
        )

        sftp_assets.append(asset)

    return sftp_assets
