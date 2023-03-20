# import pendulum
from dagster import (  # DailyPartitionsDefinition,
    FreshnessPolicy,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    TimeWindowPartitionsDefinition,
    config_from_files,
)

from teamster.core.deanslist.assets import build_deanslist_endpoint_asset
from teamster.core.utils.variables import LOCAL_TIME_ZONE

from .. import CODE_LOCATION

school_ids = config_from_files(
    [f"src/teamster/{CODE_LOCATION}/config/assets/deanslist/school_ids.yaml"]
)["school_ids"]

static_partitions_def = StaticPartitionsDefinition(school_ids)

multi_partitions_def = MultiPartitionsDefinition(
    partitions_defs={
        "date": TimeWindowPartitionsDefinition(
            cron_schedule="0 0 1 7 *",
            start="2016-07-01",
            fmt="%Y-%m-%d",
            timezone=LOCAL_TIME_ZONE.name,
            end_offset=1,
        ),
        "school": static_partitions_def,
    }
)

static_partition_assets = [
    build_deanslist_endpoint_asset(
        code_location=CODE_LOCATION,
        partitions_def=static_partitions_def,
        **endpoint,
    )
    for endpoint in config_from_files(
        [
            f"src/teamster/{CODE_LOCATION}/config/assets/deanslist/static-partition-assets.yaml"
        ]
    )["endpoints"]
]

multi_partition_assets = [
    build_deanslist_endpoint_asset(
        code_location=CODE_LOCATION,
        partitions_def=multi_partitions_def,
        freshness_policy=FreshnessPolicy(
            maximum_lag_minutes=1,
            cron_schedule="0 0 * * *",
            cron_schedule_timezone=LOCAL_TIME_ZONE.name,
        ),
        **endpoint,
    )
    for endpoint in config_from_files(
        [
            f"src/teamster/{CODE_LOCATION}/config/assets/deanslist/multi-partition-assets.yaml"
        ]
    )["endpoints"]
]

__all__ = [
    *static_partition_assets,
    *multi_partition_assets,
]
