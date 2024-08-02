import pathlib

from dagster import (
    MonthlyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.deanslist.schema import ASSET_SCHEMA
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.deanslist.assets import (
    build_deanslist_multi_partition_asset,
    build_deanslist_static_partition_asset,
)

DEANSLIST_STATIC_PARTITIONS_DEF = StaticPartitionsDefinition(["472", "525"])

DEANSLIST_MONTHLY_MULTI_PARTITIONS_DEF = MultiPartitionsDefinition(
    partitions_defs={
        "date": MonthlyPartitionsDefinition(
            start_date="2018-07-01", timezone=LOCAL_TIMEZONE.name, end_offset=1
        ),
        "school": DEANSLIST_STATIC_PARTITIONS_DEF,
    }
)

DEANSLIST_FISCAL_MULTI_PARTITIONS_DEF = MultiPartitionsDefinition(
    partitions_defs={
        "date": FiscalYearPartitionsDefinition(
            start_date="2018-07-01",
            start_month=7,
            timezone=LOCAL_TIMEZONE.name,
            end_offset=1,
        ),
        "school": DEANSLIST_STATIC_PARTITIONS_DEF,
    }
)

config_dir = pathlib.Path(__file__).parent / "config"

static_partitions_assets = [
    build_deanslist_static_partition_asset(
        asset_key=[CODE_LOCATION, "deanslist", e["endpoint"].replace("-", "_")],
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=DEANSLIST_STATIC_PARTITIONS_DEF,
        **e,
    )
    for e in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

monthly_multi_partitions_assets = [
    build_deanslist_multi_partition_asset(
        asset_key=[CODE_LOCATION, "deanslist", e["endpoint"].replace("-", "_")],
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=DEANSLIST_MONTHLY_MULTI_PARTITIONS_DEF,
        **e,
    )
    for e in config_from_files([f"{config_dir}/multi-partition-monthly-assets.yaml"])[
        "endpoints"
    ]
]

fiscal_multi_partitions_assets = [
    build_deanslist_multi_partition_asset(
        asset_key=[CODE_LOCATION, "deanslist", e["endpoint"].replace("-", "_")],
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=DEANSLIST_FISCAL_MULTI_PARTITIONS_DEF,
        **e,
    )
    for e in config_from_files([f"{config_dir}/multi-partition-fiscal-assets.yaml"])[
        "endpoints"
    ]
]

assets = [
    *static_partitions_assets,
    *monthly_multi_partitions_assets,
    *fiscal_multi_partitions_assets,
]
