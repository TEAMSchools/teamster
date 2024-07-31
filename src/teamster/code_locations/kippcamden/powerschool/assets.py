import pathlib

import pendulum
from dagster import MonthlyPartitionsDefinition, config_from_files

from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.assets import build_powerschool_table_asset

config_dir = pathlib.Path(__file__).parent / "config"

powerschool_table_assets_full = [
    build_powerschool_table_asset(
        code_location=CODE_LOCATION,
        local_timezone=LOCAL_TIMEZONE,
        table_name=a["asset_name"],
        partition_column=a["partition_column"],
        op_tags=a.get("op_tags"),
    )
    for a in config_from_files([(f"{config_dir}/assets-full.yaml")])["assets"]
]

powerschool_table_assets_no_partition = [
    build_powerschool_table_asset(
        code_location=CODE_LOCATION,
        local_timezone=LOCAL_TIMEZONE,
        table_name=a["asset_name"],
        op_tags=a.get("op_tags"),
    )
    for a in config_from_files([(f"{config_dir}/assets-nonpartition.yaml")])["assets"]
]

powerschool_table_assets_transaction_date = [
    build_powerschool_table_asset(
        code_location=CODE_LOCATION,
        local_timezone=LOCAL_TIMEZONE,
        table_name=a["asset_name"],
        partitions_def=FiscalYearPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            start_month=7,
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
        ),
        partition_column="transaction_date",
        op_tags=a.get("op_tags"),
    )
    for a in config_from_files([f"{config_dir}/assets-transactiondate.yaml"])["assets"]
]

powerschool_table_assets_whenmodified = [
    build_powerschool_table_asset(
        code_location=CODE_LOCATION,
        local_timezone=LOCAL_TIMEZONE,
        table_name=a["asset_name"],
        partitions_def=MonthlyPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
            end_offset=1,
        ),
        partition_column="whenmodified",
        op_tags=a.get("op_tags"),
    )
    for a in config_from_files([f"{config_dir}/assets-whenmodified.yaml"])["assets"]
]

assets = [
    *powerschool_table_assets_full,
    *powerschool_table_assets_no_partition,
    *powerschool_table_assets_transaction_date,
    *powerschool_table_assets_whenmodified,
]
