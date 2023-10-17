from dagster import (
    AutoMaterializePolicy,
    DailyPartitionsDefinition,
    DynamicPartitionsDefinition,
    config_from_files,
)

from teamster.core.adp.assets import build_wfm_asset
from teamster.core.adp.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.functions import get_avro_record_schema

from .. import CODE_LOCATION, LOCAL_TIMEZONE

config_dir = f"src/teamster/{CODE_LOCATION}/adp/config"

sftp_assets = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "adp_workforce_now", a["asset_name"]],
        ssh_resource_key="ssh_adp_workforce_now",
        avro_schema=get_avro_record_schema(
            name=a["asset_name"], fields=ASSET_FIELDS[a["asset_name"]]
        ),
        **a,
    )
    for a in config_from_files([f"{config_dir}/sftp-assets.yaml"])["assets"]
]

wfm_assets_daily = [
    build_wfm_asset(
        code_location=CODE_LOCATION,
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
