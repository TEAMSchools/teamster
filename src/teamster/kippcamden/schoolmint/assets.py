from dagster import (
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.schoolmint.assets import (
    build_schoolmint_grow_multi_partition_asset,
    build_schoolmint_grow_static_partition_asset,
)
from teamster.core.utils.variables import LOCAL_TIME_ZONE

from .. import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/config/assets/schoolmint"

static_partitions_def = StaticPartitionsDefinition(["true", "false"])

multi_partitions_def = MultiPartitionsDefinition(
    partitions_defs={
        "archived": static_partitions_def,
        "last_modified": DailyPartitionsDefinition(
            start_date="2023-04-05", timezone=LOCAL_TIME_ZONE.name, end_offset=1
        ),
    }
)

static_partition_assets = [
    build_schoolmint_grow_static_partition_asset(
        code_location=CODE_LOCATION, partitions_def=static_partitions_def, **endpoint
    )
    for endpoint in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

multi_partition_assets = [
    build_schoolmint_grow_multi_partition_asset(
        code_location=CODE_LOCATION, partitions_def=multi_partitions_def, **endpoint
    )
    for endpoint in config_from_files([f"{config_dir}/multi-partition-assets.yaml"])[
        "endpoints"
    ]
]

__all__ = [
    *static_partition_assets,
    *multi_partition_assets,
]
