import pathlib

from dagster import (
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.level_data.grow.schema import (
    ASSET_SCHEMA,
    ASSIGNMENT_SCHEMA,
    OBSERVATION_SCHEMA,
)
from teamster.libraries.level_data.grow.assets import build_grow_asset

STATIC_PARTITONS_DEF = StaticPartitionsDefinition(["t", "f"])
MULTI_PARTITIONS_DEF = MultiPartitionsDefinition(
    {
        "archived": STATIC_PARTITONS_DEF,
        "last_modified": DailyPartitionsDefinition(
            start_date="2023-07-31", timezone=str(LOCAL_TIMEZONE), end_offset=1
        ),
    }
)

key_prefix = [CODE_LOCATION, "schoolmint", "grow"]
config_dir = pathlib.Path(__file__).parent / "config"

grow_static_partition_assets = [
    build_grow_asset(
        asset_key=[*key_prefix, e["asset_name"].replace("-", "_").replace("/", "_")],
        endpoint=e["asset_name"],
        partitions_def=STATIC_PARTITONS_DEF,
        schema=ASSET_SCHEMA[e["asset_name"]],
        op_tags=e.get("op_tags"),
    )
    for e in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

assignments = build_grow_asset(
    asset_key=[*key_prefix, "assignments"],
    endpoint="assignments",
    partitions_def=MULTI_PARTITIONS_DEF,
    schema=ASSIGNMENT_SCHEMA,
)

observations = build_grow_asset(
    asset_key=[*key_prefix, "observations"],
    endpoint="observations",
    partitions_def=MULTI_PARTITIONS_DEF,
    schema=OBSERVATION_SCHEMA,
)

grow_multi_partitions_assets = [
    assignments,
    observations,
]

assets = [
    *grow_multi_partitions_assets,
    *grow_static_partition_assets,
]
