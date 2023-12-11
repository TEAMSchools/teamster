import random

from dagster import (
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    materialize,
)

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.resources import SCHOOLMINT_GROW_RESOURCE
from teamster.kipptaf.schoolmint.grow.assets import build_schoolmint_grow_asset
from teamster.staging import LOCAL_TIMEZONE

STATIC_PARTITONS_DEF = StaticPartitionsDefinition(["f"])


def _test_asset(asset_name, partition_start_date=None):
    if partition_start_date is not None:
        partitions_def = MultiPartitionsDefinition(
            {
                "archived": STATIC_PARTITONS_DEF,
                "last_modified": DailyPartitionsDefinition(
                    start_date=partition_start_date,
                    timezone=LOCAL_TIMEZONE.name,
                    end_offset=1,
                ),
            }
        )
    else:
        partitions_def = STATIC_PARTITONS_DEF

    asset = build_schoolmint_grow_asset(
        asset_name=asset_name, partitions_def=partitions_def
    )

    partition_keys = asset.partitions_def.get_partition_keys()

    result = materialize(
        assets=[asset],
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "schoolmint_grow": SCHOOLMINT_GROW_RESOURCE,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]
        .value
        > 0
    )


def test_asset_schoolmint_grow_generic_tags():
    assets = [
        "generic-tags/assignmentpresets",
        "generic-tags/courses",
        "generic-tags/eventtag1",
        "generic-tags/goaltypes",
        "generic-tags/grades",
        "generic-tags/measurementgroups",
        "generic-tags/meetingtypes",
        "generic-tags/observationtypes",
        "generic-tags/rubrictag1",
        "generic-tags/schooltag1",
        "generic-tags/tags",
        "generic-tags/usertag1",
        "generic-tags/usertypes",
    ]

    _test_asset(asset_name=assets[random.randint(a=0, b=(len(assets) - 1))])


def test_asset_schoolmint_grow_informals():
    _test_asset(asset_name="informals")


def test_asset_schoolmint_grow_measurements():
    _test_asset(asset_name="measurements")


def test_asset_schoolmint_grow_meetings():
    _test_asset(asset_name="meetings")


def test_asset_schoolmint_grow_roles():
    _test_asset(asset_name="roles")


def test_asset_schoolmint_grow_rubrics():
    _test_asset(asset_name="rubrics")


def test_asset_schoolmint_grow_schools():
    _test_asset(asset_name="schools")


def test_asset_schoolmint_grow_users():
    _test_asset(asset_name="users")


def test_asset_schoolmint_grow_videos():
    _test_asset(asset_name="videos")


def test_asset_schoolmint_grow_observations():
    _test_asset(asset_name="observations", partition_start_date="2023-07-31")


def test_asset_schoolmint_grow_assignments():
    _test_asset(asset_name="assignments", partition_start_date="2023-07-31")
