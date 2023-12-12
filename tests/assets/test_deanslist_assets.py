import random

from dagster import (
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    materialize,
)

from teamster.core.deanslist.assets import (
    build_deanslist_multi_partition_asset,
    build_deanslist_static_partition_asset,
)
from teamster.core.resources import DEANSLIST_RESOURCE, get_io_manager_gcs_avro
from teamster.staging import LOCAL_TIMEZONE

STATIC_PARTITIONS_DEF = StaticPartitionsDefinition(
    [
        "121",
        "122",
        "123",
        "124",
        "125",
        "127",
        "128",
        "129",
        "378",
        "380",
        "522",
        "523",
        "472",
        "525",
        "120",
        "126",
        "130",
        "473",
        "652",
    ]
)


def _test_asset(partition_type, asset_name, api_version, params={}):
    if partition_type == "multi":
        asset = build_deanslist_multi_partition_asset(
            code_location="staging",
            asset_name=asset_name,
            partitions_def=MultiPartitionsDefinition(
                partitions_defs={
                    "date": DailyPartitionsDefinition(
                        start_date="2023-03-23",
                        timezone=LOCAL_TIMEZONE.name,
                        end_offset=1,
                    ),
                    "school": STATIC_PARTITIONS_DEF,
                }
            ),
            api_version=api_version,
            params=params,
        )
    elif partition_type == "static":
        asset = build_deanslist_static_partition_asset(
            code_location="staging",
            asset_name=asset_name,
            partitions_def=STATIC_PARTITIONS_DEF,
            api_version=api_version,
            params=params,
        )

    partition_keys = asset.partitions_def.get_partition_keys()

    result = materialize(
        assets=[asset],
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "deanslist": DEANSLIST_RESOURCE,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]
        .value
        > 0
    )


def test_asset_deanslist_lists():
    _test_asset(partition_type="static", asset_name="lists", api_version="v1")


def test_asset_deanslist_terms():
    _test_asset(partition_type="static", asset_name="terms", api_version="v1")


def test_asset_deanslist_roster_assignments():
    _test_asset(
        partition_type="static", asset_name="roster-assignments", api_version="beta"
    )


def test_asset_deanslist_users():
    _test_asset(
        partition_type="static",
        asset_name="users",
        api_version="v1",
        params={"IncludeInactive": "Y"},
    )


def test_asset_deanslist_rosters():
    _test_asset(
        partition_type="static",
        asset_name="rosters",
        api_version="v1",
        params={"show_inactive": "Y"},
    )


"""
  - asset_name: comm-log
    api_version: v1
    params:
      IncludeDeleted: Y
      IncludePrevEnrollments: Y
"""


def test_asset_deanslist_followups():
    _test_asset(partition_type="multi", asset_name="followups", api_version="v1")


def test_asset_deanslist_behavior():
    _test_asset(
        partition_type="multi",
        asset_name="behavior",
        api_version="v1",
        params={
            "StartDate": "{start_date}",
            "EndDate": "{end_date}",
            "IncludeDeleted": "Y",
        },
    )


def test_asset_deanslist_homework():
    _test_asset(
        partition_type="multi",
        asset_name="homework",
        api_version="v1",
        params={
            "StartDate": "{start_date}",
            "EndDate": "{end_date}",
            "IncludeDeleted": "Y",
        },
    )


def test_asset_deanslist_comm_log():
    _test_asset(
        partition_type="multi",
        asset_name="comm-log",
        api_version="v1",
        params={"IncludeDeleted": "Y", "IncludePrevEnrollments": "Y"},
    )


def test_asset_deanslist_incidents():
    _test_asset(
        partition_type="multi",
        asset_name="incidents",
        api_version="v1",
        params={
            "StartDate": "{start_date}",
            "EndDate": "{end_date}",
            "IncludeDeleted": "Y",
            "cf": "Y",
        },
    )
