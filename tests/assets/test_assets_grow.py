import random

from dagster import TextMetadataValue, materialize
from dagster._core.events import StepMaterializationData
from dagster_shared import check

from teamster.core.resources import get_io_manager_gcs_avro


def _test_asset(asset, partition_key=None):
    from teamster.code_locations.kipptaf.resources import GROW_RESOURCE

    if partition_key is None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "grow": GROW_RESOURCE,
        },
    )

    assert result.success
    asset_materialization_event = result.get_asset_materialization_events()[0]
    event_specific_data = check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )
    records = check.inst(
        event_specific_data.materialization.metadata["records"].value, int
    )
    assert records > 0
    extras = check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )
    assert extras.text == ""


def test_asset_grow_generic_tags_assignmentpresets():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_assignmentpresets"
        ][0],
        partition_key="f",
    )


def test_asset_grow_generic_tags_courses():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_courses"
        ][0],
        partition_key="f",
    )


def test_asset_grow_generic_tags_eventtag1():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_eventtag1"
        ][0],
        partition_key="t",
    )


def test_asset_grow_generic_tags_goaltypes():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_goaltypes"
        ][0],
        partition_key="f",
    )


def test_asset_grow_generic_tags_grades():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_grades"
        ][0],
        partition_key="f",
    )


def test_asset_grow_generic_tags_measurementgroups():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_measurementgroups"
        ][0],
        partition_key="f",
    )


def test_asset_grow_generic_tags_meetingtypes():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_meetingtypes"
        ][0],
        partition_key="f",
    )


def test_asset_grow_generic_tags_observationtypes():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_observationtypes"
        ][0],
        partition_key="f",
    )


def test_asset_grow_generic_tags_rubrictag1():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_rubrictag1"
        ][0],
        partition_key="f",
    )


def test_asset_grow_generic_tags_schooltag1():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_schooltag1"
        ][0],
        partition_key="f",
    )


def test_asset_grow_generic_tags_tags():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_tags"
        ][0],
        partition_key="t",
    )


def test_asset_grow_generic_tags_usertag1():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_usertag1"
        ][0],
        partition_key="t",
    )


def test_asset_grow_generic_tags_usertypes():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a
            for a in grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_usertypes"
        ][0],
        partition_key="f",
    )


def test_asset_grow_informals():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a for a in grow_static_partition_assets if a.key.path[-1] == "informals"
        ][0],
    )


def test_asset_grow_measurements():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[
            a for a in grow_static_partition_assets if a.key.path[-1] == "measurements"
        ][0],
    )


def test_asset_grow_meetings():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[a for a in grow_static_partition_assets if a.key.path[-1] == "meetings"][
            0
        ],
    )


def test_asset_grow_roles():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[a for a in grow_static_partition_assets if a.key.path[-1] == "roles"][0],
    )


def test_asset_grow_rubrics():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[a for a in grow_static_partition_assets if a.key.path[-1] == "rubrics"][
            0
        ],
    )


def test_asset_grow_schools():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[a for a in grow_static_partition_assets if a.key.path[-1] == "schools"][
            0
        ],
    )


def test_asset_grow_users():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[a for a in grow_static_partition_assets if a.key.path[-1] == "users"][0],
        partition_key="f",
    )


def test_asset_grow_videos():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        asset=[a for a in grow_static_partition_assets if a.key.path[-1] == "videos"][
            0
        ],
    )


def test_asset_grow_observations():
    from teamster.code_locations.kipptaf.level_data.grow.assets import observations

    _test_asset(asset=observations)


def test_asset_grow_assignments():
    from teamster.code_locations.kipptaf.level_data.grow.assets import assignments

    _test_asset(asset=assignments, partition_key="f|2024-09-16")
