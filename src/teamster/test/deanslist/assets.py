import pendulum
from dagster import (
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.deanslist.assets import build_deanslist_endpoint_asset
from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.test import CODE_LOCATION

school_ids = config_from_files(
    [f"src/teamster/{CODE_LOCATION}/deanslist/config/school_ids.yaml"]
)["school_ids"]

static_partitions_def = StaticPartitionsDefinition(school_ids)
multi_partitions_def = MultiPartitionsDefinition(
    partitions_defs={
        "time_window": DailyPartitionsDefinition(
            start_date="2023-02-01", timezone=LOCAL_TIME_ZONE.name
        ),
        "school": static_partitions_def,
    }
)


nonpartition_assets = [
    build_deanslist_endpoint_asset(
        code_location=CODE_LOCATION,
        # school_ids=school_ids,
        partitions_def=static_partitions_def,
        **endpoint,
    )
    for endpoint in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/deanslist/config/nonpartition-assets.yaml"]
    )["endpoints"]
]

partition_assets = [
    build_deanslist_endpoint_asset(
        code_location=CODE_LOCATION,
        # school_ids=school_ids,
        partitions_def=multi_partitions_def,
        inception_date=pendulum.date(2016, 7, 1),
        **endpoint,
    )
    for endpoint in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/deanslist/config/partition-assets.yaml"]
    )["endpoints"]
]
