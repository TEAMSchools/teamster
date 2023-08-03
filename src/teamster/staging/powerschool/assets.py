import pendulum
from dagster import config_from_files

from teamster.core.powerschool.assets import build_powerschool_table_asset
from teamster.core.utils.classes import FiscalYearPartitionsDefinition

from .. import CODE_LOCATION, LOCAL_TIMEZONE

config_dir = f"src/teamster/{CODE_LOCATION}/powerschool/config"

full_assets = [
    build_powerschool_table_asset(**cfg, code_location=CODE_LOCATION)
    for cfg in config_from_files([(f"{config_dir}/assets-full.yaml")])["assets"]
]

nonpartition_assets = [
    build_powerschool_table_asset(**cfg, code_location=CODE_LOCATION)
    for cfg in config_from_files([(f"{config_dir}/assets-nonpartition.yaml")])["assets"]
]

transaction_date_partition_assets = [
    build_powerschool_table_asset(
        **asset,
        code_location=CODE_LOCATION,
        partitions_def=FiscalYearPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            start_month=7,
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
        ),
        partition_column="transaction_date",
    )
    for asset in config_from_files([f"{config_dir}/assets-transactiondate.yaml"])[
        "assets"
    ]
]

whenmodified_partition_assets = [
    build_powerschool_table_asset(
        **asset,
        code_location=CODE_LOCATION,
        partitions_def=FiscalYearPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            start_month=7,
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
        ),
        partition_column="whenmodified",
    )
    for asset in config_from_files([f"{config_dir}/assets-whenmodified.yaml"])["assets"]
]

partition_assets = [
    *transaction_date_partition_assets,
    *whenmodified_partition_assets,
]

__all__ = [
    *full_assets,
    *transaction_date_partition_assets,
    *whenmodified_partition_assets,
    *nonpartition_assets,
]
