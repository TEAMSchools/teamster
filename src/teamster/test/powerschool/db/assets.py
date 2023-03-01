from dagster import DynamicPartitionsDefinition, config_from_files

from teamster.core.powerschool.db.assets import build_powerschool_table_asset
from teamster.test import CODE_LOCATION

dynamic_partitions_def = DynamicPartitionsDefinition(name="datetime")

nonpartition_assets = [
    build_powerschool_table_asset(**cfg, code_location=CODE_LOCATION)
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-nonpartition.yaml"]
    )["assets"]
]

transactiondate_assets = [
    build_powerschool_table_asset(
        **cfg,
        code_location=CODE_LOCATION,
        partitions_def=dynamic_partitions_def,
        where_column="transaction_date",
    )
    for cfg in config_from_files(
        [
            f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-transactiondate.yaml"
        ]
    )["assets"]
]

whenmodified_assets = [
    build_powerschool_table_asset(
        **cfg,
        code_location=CODE_LOCATION,
        partitions_def=dynamic_partitions_def,
        where_column="whenmodified",
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-whenmodified.yaml"]
    )["assets"]
]

partition_assets = transactiondate_assets + whenmodified_assets
all_assets = partition_assets + nonpartition_assets
