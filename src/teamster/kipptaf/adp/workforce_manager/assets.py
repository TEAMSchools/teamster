from dagster import (
    AutoMaterializePolicy,
    DailyPartitionsDefinition,
    DynamicPartitionsDefinition,
    config_from_files,
)

from teamster.core.adp.workforce_manager.assets import build_wfm_asset

from ... import CODE_LOCATION, LOCAL_TIMEZONE

adp_wfm_assets_daily = [
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
    for a in config_from_files(
        [
            f"src/teamster/{CODE_LOCATION}/adp/workforce_manager/config/wfm-assets-daily.yaml"
        ]
    )["assets"]
]

adp_wfm_assets_dynamic = [
    build_wfm_asset(
        code_location=CODE_LOCATION,
        date_partitions_def=DynamicPartitionsDefinition(
            name=f"{CODE_LOCATION}__adp_workforce_manager__{a['asset_name']}_date"
        ),
        auto_materialize_policy=AutoMaterializePolicy.eager(),
        **a,
    )
    for a in config_from_files(
        [
            f"src/teamster/{CODE_LOCATION}/adp/workforce_manager/config/wfm-assets-dynamic.yaml"
        ]
    )["assets"]
]
