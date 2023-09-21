from dagster import (
    AutoMaterializePolicy,
    DailyPartitionsDefinition,
    DynamicPartitionsDefinition,
    config_from_files,
)

from teamster.core.adp.assets import build_wfm_asset
from teamster.core.adp.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset

from .. import CODE_LOCATION, LOCAL_TIMEZONE

config_dir = f"src/teamster/{CODE_LOCATION}/adp/config"

sftp_assets = [
    build_sftp_asset(
        code_location=CODE_LOCATION,
        source_system="adp_workforce_now",
        asset_fields=ASSET_FIELDS,
        **a,
    )
    for a in config_from_files([f"{config_dir}/sftp-assets.yaml"])["assets"]
]

wfm_assets_daily = [
    build_wfm_asset(
        code_location=CODE_LOCATION,
        source_system="adp_workforce_manager",
        date_partitions_def=DailyPartitionsDefinition(
            start_date=a["partition_start_date"],
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%d",
            end_offset=1,
        ),
        auto_materialize_policy=AutoMaterializePolicy.eager(),
        **a,
    )
    for a in config_from_files([f"{config_dir}/wfm-assets-daily.yaml"])["assets"]
]

wfm_assets_dynamic = [
    build_wfm_asset(
        code_location=CODE_LOCATION,
        source_system="adp_workforce_manager",
        date_partitions_def=DynamicPartitionsDefinition(
            name=f"{CODE_LOCATION}__adp_workforce_manager__{a['asset_name']}_date"
        ),
        auto_materialize_policy=AutoMaterializePolicy.eager(),
        **a,
    )
    for a in config_from_files([f"{config_dir}/wfm-assets-dynamic.yaml"])["assets"]
]

__all__ = [
    *sftp_assets,
    *wfm_assets_daily,
    *wfm_assets_dynamic,
]
