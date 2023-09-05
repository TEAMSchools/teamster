from dagster import AutoMaterializePolicy, DailyPartitionsDefinition, config_from_files

from teamster.core.edplan.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset


def build_edplan_sftp_asset(config_dir, code_location, timezone):
    sftp_assets = []

    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]:
        asset = build_sftp_asset(
            code_location=code_location,
            source_system="edplan",
            asset_fields=ASSET_FIELDS,
            partitions_def=DailyPartitionsDefinition(
                start_date=a["partition_start_date"],
                timezone=timezone.name,
                fmt="%Y-%m-%d",
                end_offset=1,
            ),
            auto_materialize_policy=AutoMaterializePolicy.eager(),
            **a,
        )

        sftp_assets.append(asset)

    return sftp_assets
