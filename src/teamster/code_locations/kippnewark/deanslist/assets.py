import pathlib

from dagster import (
    MonthlyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.deanslist.schema import (
    ASSET_SCHEMA,
    BEHAVIOR_SCHEMA,
)
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.deanslist.assets import (
    build_deanslist_multi_partition_asset,
    build_deanslist_paginated_multi_partition_asset,
    build_deanslist_static_partition_asset,
)

DEANSLIST_STATIC_PARTITIONS_DEF = StaticPartitionsDefinition(
    ["121", "122", "123", "124", "125", "127", "128", "129", "378", "380", "522", "523"]
)

DEANSLIST_FISCAL_MULTI_PARTITIONS_DEF = MultiPartitionsDefinition(
    partitions_defs={
        "school": DEANSLIST_STATIC_PARTITIONS_DEF,
        "date": FiscalYearPartitionsDefinition(
            start_date="2016-07-01",
            start_month=7,
            timezone=str(LOCAL_TIMEZONE),
            end_offset=1,
        ),
    }
)

config_dir = pathlib.Path(__file__).parent / "config"

static_partitioned_assets = [
    build_deanslist_static_partition_asset(
        code_location=CODE_LOCATION,
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=DEANSLIST_STATIC_PARTITIONS_DEF,
        **e,
    )
    for e in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

month_partitioned_assets = [
    build_deanslist_multi_partition_asset(
        code_location=CODE_LOCATION,
        api_version="v1",
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=MultiPartitionsDefinition(
            partitions_defs={
                "school": DEANSLIST_STATIC_PARTITIONS_DEF,
                "date": MonthlyPartitionsDefinition(
                    start_date="2016-07-01", timezone=str(LOCAL_TIMEZONE), end_offset=1
                ),
            }
        ),
        **e,
    )
    for e in config_from_files([f"{config_dir}/multi-partition-monthly-assets.yaml"])[
        "endpoints"
    ]
]

year_partitioned_assets = [
    build_deanslist_multi_partition_asset(
        code_location=CODE_LOCATION,
        api_version="v1",
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=DEANSLIST_FISCAL_MULTI_PARTITIONS_DEF,
        **e,
    )
    for e in config_from_files([f"{config_dir}/multi-partition-fiscal-assets.yaml"])[
        "endpoints"
    ]
]

year_partitioned_assets.append(
    build_deanslist_paginated_multi_partition_asset(
        code_location=CODE_LOCATION,
        endpoint="behavior",
        api_version="v1",
        schema=BEHAVIOR_SCHEMA,
        partitions_def=DEANSLIST_FISCAL_MULTI_PARTITIONS_DEF,
    )
)

assets = [
    *static_partitioned_assets,
    *month_partitioned_assets,
    *year_partitioned_assets,
]
