from dagster import DailyPartitionsDefinition, config_from_files

from teamster.core.powerschool.db.assets import build_powerschool_table_asset
from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kippnewark import CODE_LOCATION

daily_partitions_def = DailyPartitionsDefinition(
    start_date="2023-02-28T00:00:00.000000",
    timezone=LOCAL_TIME_ZONE.name,
    fmt="%Y-%m-%dT%H:%M:%S.%f",
    end_offset=1,
)

nonpartition_assets = [
    build_powerschool_table_asset(**cfg, code_location=CODE_LOCATION)
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-nonpartition.yaml"]
    )["assets"]
]

partition_assets = []
for foo in ["transactiondate", "whenmodified"]:
    config = config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-{foo}.yaml"]
    )

    partition_column = config["partition_column"]
    for asset in config["assets"]:
        partition_assets.append(
            build_powerschool_table_asset(
                **asset,
                code_location=CODE_LOCATION,
                partitions_def=daily_partitions_def,
                metadata={"partition_column": partition_column},
            )
        )

all_assets = partition_assets + nonpartition_assets
