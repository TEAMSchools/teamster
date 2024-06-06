import pathlib

import pendulum
from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    MonthlyPartitionsDefinition,
    config_from_files,
)

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.assets import build_powerschool_table_asset

config_dir = pathlib.Path(__file__).parent / "config"

full_assets = [
    build_powerschool_table_asset(
        asset_key=[CODE_LOCATION, "powerschool", a["asset_name"]],
        local_timezone=LOCAL_TIMEZONE,
        **a,
    )
    for a in config_from_files([(f"{config_dir}/assets-full.yaml")])["assets"]
]

nonpartition_assets = [
    build_powerschool_table_asset(
        asset_key=[CODE_LOCATION, "powerschool", a["asset_name"]],
        local_timezone=LOCAL_TIMEZONE,
        op_tags={MAX_RUNTIME_SECONDS_TAG: (60 * 10)},
        **a,
    )
    for a in config_from_files([(f"{config_dir}/assets-nonpartition.yaml")])["assets"]
]

transaction_date_partition_assets = [
    build_powerschool_table_asset(
        asset_key=[CODE_LOCATION, "powerschool", a["asset_name"]],
        local_timezone=LOCAL_TIMEZONE,
        partitions_def=FiscalYearPartitionsDefinition(
            start_date=pendulum.datetime(year=2018, month=7, day=1),
            start_month=7,
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
        ),
        partition_column="transaction_date",
        op_tags={MAX_RUNTIME_SECONDS_TAG: (60 * 10)},
        **a,
    )
    for a in config_from_files([f"{config_dir}/assets-transactiondate.yaml"])["assets"]
]

whenmodified_assets = [
    build_powerschool_table_asset(
        asset_key=[CODE_LOCATION, "powerschool", a["asset_name"]],
        local_timezone=LOCAL_TIMEZONE,
        partitions_def=MonthlyPartitionsDefinition(
            start_date=pendulum.datetime(year=2018, month=7, day=1),
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
            end_offset=1,
        ),
        partition_column="whenmodified",
        op_tags={MAX_RUNTIME_SECONDS_TAG: (60 * 10)},
        **a,
    )
    for a in config_from_files([f"{config_dir}/assets-whenmodified.yaml"])["assets"]
]

dcid_assets = [
    build_powerschool_table_asset(
        asset_key=[CODE_LOCATION, "powerschool", "storedgrades_dcid"],
        local_timezone=LOCAL_TIMEZONE,
        table_name="storedgrades",
        select_columns=["dcid"],
    )
]

partition_assets = [
    *whenmodified_assets,
    *transaction_date_partition_assets,
]

assets = [
    *whenmodified_assets,
    *full_assets,
    *nonpartition_assets,
    *transaction_date_partition_assets,
    *dcid_assets,
]
