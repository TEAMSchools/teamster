from dagster import DynamicPartitionsDefinition, config_from_files

from teamster.core.powerschool.assets import build_powerschool_table_asset

from .. import CODE_LOCATION, CURRENT_FISCAL_YEAR

config_dir = f"src/teamster/{CODE_LOCATION}/powerschool/config"

nonpartition_assets = [
    build_powerschool_table_asset(**cfg, code_location=CODE_LOCATION)
    for cfg in config_from_files([(f"{config_dir}/assets-nonpartition.yaml")])["assets"]
]

transaction_date_partition_assets = [
    build_powerschool_table_asset(
        **asset,
        code_location=CODE_LOCATION,
        partitions_def=DynamicPartitionsDefinition(
            name=f"{CODE_LOCATION}_powerschool_{asset['asset_name']}_{CURRENT_FISCAL_YEAR.fiscal_year}"
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
        partitions_def=DynamicPartitionsDefinition(
            name=f"{CODE_LOCATION}_powerschool_{asset['asset_name']}_{CURRENT_FISCAL_YEAR.fiscal_year}"
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
    *transaction_date_partition_assets,
    *whenmodified_partition_assets,
    *nonpartition_assets,
]
