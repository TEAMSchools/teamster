from dagster import (
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.deanslist.assets import (
    build_deanslist_multi_partition_asset,
    build_deanslist_static_partition_asset,
)

from .. import CODE_LOCATION, LOCAL_TIMEZONE

config_dir = f"src/teamster/{CODE_LOCATION}/deanslist/config"

school_ids = config_from_files([f"{config_dir}/school_ids.yaml"])["school_ids"]

static_partitions_def = StaticPartitionsDefinition(school_ids)

multi_partitions_def = MultiPartitionsDefinition(
    partitions_defs={
        "date": DailyPartitionsDefinition(
            start_date="2023-03-23", timezone=LOCAL_TIMEZONE.name, end_offset=1
        ),
        "school": static_partitions_def,
    }
)

static_partition_assets = [
    build_deanslist_multi_partition_asset(
        code_location=CODE_LOCATION, partitions_def=static_partitions_def, **endpoint
    )
    for endpoint in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

multi_partition_assets = [
    build_deanslist_static_partition_asset(
        code_location=CODE_LOCATION,
        partitions_def=multi_partitions_def,
        # inception_date=pendulum.date(2016, 7, 1),
        **endpoint,
    )
    for endpoint in config_from_files([f"{config_dir}/multi-partition-assets.yaml"])[
        "endpoints"
    ]
]

__all__ = [
    *static_partition_assets,
    *multi_partition_assets,
]
