import pendulum
from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    MonthlyPartitionsDefinition,
    config_from_files,
)

from teamster.core.powerschool.assets import build_powerschool_table_asset
from teamster.core.utils.classes import FiscalYearPartitionsDefinition

from .. import CODE_LOCATION, LOCAL_TIMEZONE

config_dir = f"src/teamster/{CODE_LOCATION}/powerschool/config"

full_assets = [
    build_powerschool_table_asset(
        **cfg,
        code_location=CODE_LOCATION,
        local_timezone=LOCAL_TIMEZONE,
        op_tags={MAX_RUNTIME_SECONDS_TAG: (60 * 10)},
    )
    for cfg in config_from_files([(f"{config_dir}/assets-full.yaml")])["assets"]
]

nonpartition_assets = [
    build_powerschool_table_asset(
        **cfg,
        code_location=CODE_LOCATION,
        local_timezone=LOCAL_TIMEZONE,
        op_tags={MAX_RUNTIME_SECONDS_TAG: (60 * 10)},
    )
    for cfg in config_from_files([(f"{config_dir}/assets-nonpartition.yaml")])["assets"]
]

transaction_date_partition_assets = [
    build_powerschool_table_asset(
        **asset,
        code_location=CODE_LOCATION,
        local_timezone=LOCAL_TIMEZONE,
        partitions_def=FiscalYearPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            start_month=7,
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
        ),
        partition_column="transaction_date",
        op_tags={MAX_RUNTIME_SECONDS_TAG: (60 * 10)},
    )
    for asset in config_from_files([f"{config_dir}/assets-transactiondate.yaml"])[
        "assets"
    ]
]

whenmodified_assets = [
    build_powerschool_table_asset(
        **asset,
        code_location=CODE_LOCATION,
        local_timezone=LOCAL_TIMEZONE,
        partitions_def=MonthlyPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
            end_offset=1,
        ),
        partition_column="whenmodified",
        op_tags={MAX_RUNTIME_SECONDS_TAG: (60 * 10)},
    )
    for asset in config_from_files([f"{config_dir}/assets-whenmodified.yaml"])["assets"]
]

dcid_assets = [
    build_powerschool_table_asset(
        code_location=CODE_LOCATION,
        asset_name="storedgrades_dcid",
        local_timezone=LOCAL_TIMEZONE,
        table_name="storedgrades",
        select_columns=["dcid"],
    )
]

partition_assets = [
    *whenmodified_assets,
    *transaction_date_partition_assets,
]

_all = [
    *whenmodified_assets,
    *full_assets,
    *nonpartition_assets,
    *transaction_date_partition_assets,
    *dcid_assets,
]
