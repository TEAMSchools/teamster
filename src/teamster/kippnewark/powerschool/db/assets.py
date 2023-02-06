from dagster import HourlyPartitionsDefinition, config_from_files

from teamster.core.powerschool.db.assets import build_powerschool_table_asset
from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kippnewark import CODE_LOCATION

hourly_partitions_def = HourlyPartitionsDefinition(
    start_date="2023-02-01T00:00:00.000000",
    timezone=LOCAL_TIME_ZONE.name,
    fmt="%Y-%m-%dT%H:%M:%S.%f",
)

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
        partitions_def=hourly_partitions_def,
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
        partitions_def=hourly_partitions_def,
        where_column="whenmodified",
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-whenmodified.yaml"]
    )["assets"]
]
