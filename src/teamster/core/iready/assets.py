from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.iready.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset


# TODO: completely refactor
def build_iready_sftp_asset(config_dir, code_location, timezone):
    sftp_assets = []

    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]:
        asset = build_sftp_asset(
            code_location=code_location,
            source_system="iready",
            asset_fields=ASSET_FIELDS,
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

        sftp_assets.append(asset)

    return sftp_assets
