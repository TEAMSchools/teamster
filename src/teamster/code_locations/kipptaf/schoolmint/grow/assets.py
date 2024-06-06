import pathlib

from dagster import (
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.schoolmint.grow.schema import ASSET_SCHEMA
from teamster.libraries.schoolmint.grow.assets import build_schoolmint_grow_asset

STATIC_PARTITONS_DEF = StaticPartitionsDefinition(["t", "f"])

config_dir = pathlib.Path(__file__).parent / "config"

static_partition_assets = [
    build_schoolmint_grow_asset(
        asset_key=[
            CODE_LOCATION,
            "schoolmint",
            "grow",
            e["asset_name"].replace("-", "_").replace("/", "_"),
        ],
        endpoint=e["asset_name"],
        partitions_def=STATIC_PARTITONS_DEF,
        schema=ASSET_SCHEMA[e["asset_name"]],
    )
    for e in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

multi_partition_assets = [
    build_schoolmint_grow_asset(
        asset_key=[CODE_LOCATION, "schoolmint", "grow", e["asset_name"]],
        endpoint=e["asset_name"],
        partitions_def=MultiPartitionsDefinition(
            {
                "archived": STATIC_PARTITONS_DEF,
                "last_modified": DailyPartitionsDefinition(
                    start_date=e["start_date"],
                    timezone=LOCAL_TIMEZONE.name,
                    end_offset=1,
                ),
            }
        ),
        schema=ASSET_SCHEMA[e["asset_name"]],
    )
    for e in config_from_files([f"{config_dir}/multi-partition-assets.yaml"])[
        "endpoints"
    ]
]

assets = [
    *static_partition_assets,
    *multi_partition_assets,
]
