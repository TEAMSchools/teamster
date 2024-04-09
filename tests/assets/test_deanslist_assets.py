import random

from dagster import (
    MonthlyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    materialize,
)

from teamster.core.deanslist.assets import (
    build_deanslist_multi_partition_asset,
    build_deanslist_static_partition_asset,
)
from teamster.core.resources import DEANSLIST_RESOURCE, get_io_manager_gcs_avro
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.staging import LOCAL_TIMEZONE

STATIC_PARTITIONS_DEF = StaticPartitionsDefinition(
    [
        "120",
        "121",
        "122",
        "123",
        "124",
        "125",
        "126",
        "127",
        "128",
        "129",
        "130",
        "378",
        "380",
        "472",
        "473",
        "522",
        "523",
        "525",
        "652",
    ]
)


def _test_asset(
    partition_type,
    asset_name,
    api_version,
    params: dict | None = None,
    partition_key: str | None = None,
):
    if params is None:
        params = {}

    if partition_type == "monthly":
        asset = build_deanslist_multi_partition_asset(
            code_location="staging",
            asset_name=asset_name,
            partitions_def=MultiPartitionsDefinition(
                partitions_defs={
                    "date": MonthlyPartitionsDefinition(
                        start_date="2016-07-01",
                        timezone=LOCAL_TIMEZONE.name,
                        end_offset=1,
                    ),
                    "school": STATIC_PARTITIONS_DEF,
                }
            ),
            api_version=api_version,
            params=params,
        )
    elif partition_type == "fiscal":
        asset = build_deanslist_multi_partition_asset(
            code_location="staging",
            asset_name=asset_name,
            partitions_def=MultiPartitionsDefinition(
                partitions_defs={
                    "date": FiscalYearPartitionsDefinition(
                        start_date="2016-07-01",
                        start_month=7,
                        timezone=LOCAL_TIMEZONE.name,
                        end_offset=1,
                    ),
                    "school": STATIC_PARTITIONS_DEF,
                }
            ),
            api_version=api_version,
            params=params,
        )
    else:
        asset = build_deanslist_static_partition_asset(
            code_location="staging",
            asset_name=asset_name,
            partitions_def=STATIC_PARTITIONS_DEF,
            api_version=api_version,
            params=params,
        )

    if partition_key is None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "deanslist": DEANSLIST_RESOURCE,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]  # type: ignore
        .value
        > 0
    )
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""


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


def test_asset_deanslist_behavior():
    _test_asset(
        partition_type="monthly",
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
        partition_type="monthly",
        asset_name="homework",
        api_version="v1",
        params={
            "StartDate": "{start_date}",
            "EndDate": "{end_date}",
            "IncludeDeleted": "Y",
        },
    )


def test_asset_deanslist_incidents():
    _test_asset(
        partition_type="monthly",
        asset_name="incidents",
        api_version="v1",
        params={"IncludeDeleted": "Y", "cf": "Y"},
    )


def test_asset_deanslist_comm_log():
    _test_asset(
        partition_type="fiscal",
        asset_name="comm-log",
        api_version="v1",
        params={"IncludeDeleted": "Y", "IncludePrevEnrollments": "Y"},
    )


def test_asset_deanslist_followups():
    _test_asset(partition_type="fiscal", asset_name="followups", api_version="v1")


def test_asset_deanslist_students():
    _test_asset(
        partition_type="static",
        asset_name="students",
        api_version="v1",
        params={
            "IncludeCustomFields": "Y",
            "IncludeUnenrolled": "Y",
            "IncludeParents": "Y",
        },
    )
