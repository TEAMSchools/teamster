import pathlib

from dagster import (
    MonthlyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.deanslist.schema import ASSET_SCHEMA
from teamster.libraries.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.deanslist.assets import (
    build_deanslist_multi_partition_asset,
    build_deanslist_static_partition_asset,
)

static_partitions_def = StaticPartitionsDefinition(
    ["121", "122", "123", "124", "125", "127", "128", "129", "378", "380", "522", "523"]
)

config_dir = pathlib.Path(__file__).parent / "config"

static_partition_assets = [
    build_deanslist_static_partition_asset(
        asset_key=[CODE_LOCATION, "deanslist", e["endpoint"].replace("-", "_")],
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=static_partitions_def,
        **e,
    )
    for e in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

multi_partition_monthly_assets = [
    build_deanslist_multi_partition_asset(
        asset_key=[CODE_LOCATION, "deanslist", e["endpoint"].replace("-", "_")],
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=MultiPartitionsDefinition(
            partitions_defs={
                "date": MonthlyPartitionsDefinition(
                    start_date="2016-07-01", timezone=LOCAL_TIMEZONE.name, end_offset=1
                ),
                "school": static_partitions_def,
            }
        ),
        **e,
    )
    for e in config_from_files([f"{config_dir}/multi-partition-monthly-assets.yaml"])[
        "endpoints"
    ]
]

multi_partition_fiscal_assets = [
    build_deanslist_multi_partition_asset(
        asset_key=[CODE_LOCATION, "deanslist", e["endpoint"].replace("-", "_")],
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=MultiPartitionsDefinition(
            partitions_defs={
                "date": FiscalYearPartitionsDefinition(
                    start_date="2016-07-01",
                    start_month=7,
                    timezone=LOCAL_TIMEZONE.name,
                    end_offset=1,
                ),
                "school": static_partitions_def,
            }
        ),
        **e,
    )
    for e in config_from_files([f"{config_dir}/multi-partition-fiscal-assets.yaml"])[
        "endpoints"
    ]
]

assets = [
    *static_partition_assets,
    *multi_partition_monthly_assets,
    *multi_partition_fiscal_assets,
]
