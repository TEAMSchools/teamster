import pathlib
from datetime import datetime

from dagster import MonthlyPartitionsDefinition, config_from_files

from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.assets import build_powerschool_table_asset

config_dir = pathlib.Path(__file__).parent / "config"

powerschool_table_assets_full = [
    build_powerschool_table_asset(
        code_location=CODE_LOCATION,
        table_name=a["asset_name"],
        partition_column=a["partition_column"],
        select_columns=a.get("select_columns"),
        op_tags=a.get("op_tags"),
    )
    for a in config_from_files([(f"{config_dir}/assets-full.yaml")])["assets"]
]

powerschool_table_assets_no_partition = [
    build_powerschool_table_asset(
        code_location=CODE_LOCATION,
        table_name=a["asset_name"],
        select_columns=a.get("select_columns"),
        op_tags=a.get("op_tags"),
    )
    for a in config_from_files([(f"{config_dir}/assets-nonpartition.yaml")])["assets"]
]

powerschool_table_assets_nightly = [
    build_powerschool_table_asset(
        code_location=CODE_LOCATION,
        table_name=a["asset_name"],
        partition_column=a["partition_column"],
        select_columns=a.get("select_columns"),
        op_tags=a.get("op_tags"),
    )
    for a in config_from_files([(f"{config_dir}/assets-nightly.yaml")])["assets"]
]

powerschool_table_assets_transaction_date = [
    build_powerschool_table_asset(
        code_location=CODE_LOCATION,
        table_name=a["asset_name"],
        partitions_def=FiscalYearPartitionsDefinition(
            start_date=datetime(year=2016, month=7, day=1),
            start_month=7,
            timezone=str(LOCAL_TIMEZONE),
            fmt="%Y-%m-%dT%H:%M:%S%z",
        ),
        partition_column="transaction_date",
        op_tags=a.get("op_tags"),
    )
    for a in config_from_files([f"{config_dir}/assets-transactiondate.yaml"])["assets"]
]

powerschool_table_assets_gradebook_full = [
    build_powerschool_table_asset(
        code_location=CODE_LOCATION,
        table_name=a["asset_name"],
        partition_column="whenmodified",
        select_columns=a.get("select_columns"),
        op_tags=a.get("op_tags"),
    )
    for a in config_from_files([(f"{config_dir}/assets-gradebook-full.yaml")])["assets"]
]

powerschool_table_assets_gradebook_monthly = [
    build_powerschool_table_asset(
        code_location=CODE_LOCATION,
        table_name=a["asset_name"],
        partitions_def=MonthlyPartitionsDefinition(
            start_date=datetime(year=2016, month=7, day=1),
            timezone=str(LOCAL_TIMEZONE),
            fmt="%Y-%m-%dT%H:%M:%S%z",
            end_offset=1,
        ),
        partition_column="whenmodified",
        op_tags=a.get("op_tags"),
    )
    for a in (
        config_from_files([f"{config_dir}/assets-gradebook-monthly.yaml"])["assets"]
    )
]

assets = [
    *powerschool_table_assets_full,
    *powerschool_table_assets_gradebook_full,
    *powerschool_table_assets_gradebook_monthly,
    *powerschool_table_assets_nightly,
    *powerschool_table_assets_no_partition,
    *powerschool_table_assets_transaction_date,
]
