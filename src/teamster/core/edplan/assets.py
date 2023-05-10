from dagster import DailyPartitionsDefinition, config_from_files

from teamster.core.edplan.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.variables import LOCAL_TIME_ZONE


def build_edplan_sftp_asset(config_dir, code_location):
    sftp_assets = []

    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]:
        asset = build_sftp_asset(
            code_location=code_location,
            source_system="edplan",
            asset_fields=ASSET_FIELDS,
            partitions_def=DailyPartitionsDefinition(
                start_date=a["partition_start_date"],
                timezone=LOCAL_TIME_ZONE.name,
                fmt="%Y-%m-%d",
                end_offset=1,
            ),
            **a,
        )

        sftp_assets.append(asset)

    return sftp_assets
