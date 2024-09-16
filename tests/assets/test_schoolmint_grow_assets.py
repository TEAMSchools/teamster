import random

from dagster import TextMetadataValue, _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kipptaf.resources import SCHOOLMINT_GROW_RESOURCE
from teamster.code_locations.kipptaf.schoolmint.grow.assets import (
    assignments,
    observations,
    schoolmint_grow_static_partition_assets,
)
from teamster.core.resources import get_io_manager_gcs_avro


def _test_asset(asset, partition_key=None):
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
            "schoolmint_grow": SCHOOLMINT_GROW_RESOURCE,
        },
    )

    assert result.success
    asset_materialization_event = result.get_asset_materialization_events()[0]
    event_specific_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )
    records = _check.inst(
        event_specific_data.materialization.metadata["records"].value, int
    )
    assert records > 0
    extras = _check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )
    assert extras.text == ""


def test_asset_schoolmint_grow_generic_tags_assignmentpresets():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_assignmentpresets"
        ][0],
        partition_key="f",
    )


def test_asset_schoolmint_grow_generic_tags_courses():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_courses"
        ][0],
        partition_key="f",
    )


def test_asset_schoolmint_grow_generic_tags_eventtag1():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_eventtag1"
        ][0],
        partition_key="t",
    )


def test_asset_schoolmint_grow_generic_tags_goaltypes():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_goaltypes"
        ][0],
        partition_key="f",
    )


def test_asset_schoolmint_grow_generic_tags_grades():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_grades"
        ][0],
        partition_key="f",
    )


def test_asset_schoolmint_grow_generic_tags_measurementgroups():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_measurementgroups"
        ][0],
        partition_key="f",
    )


def test_asset_schoolmint_grow_generic_tags_meetingtypes():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_meetingtypes"
        ][0],
        partition_key="f",
    )


def test_asset_schoolmint_grow_generic_tags_observationtypes():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_observationtypes"
        ][0],
        partition_key="f",
    )


def test_asset_schoolmint_grow_generic_tags_rubrictag1():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_rubrictag1"
        ][0],
        partition_key="f",
    )


def test_asset_schoolmint_grow_generic_tags_schooltag1():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_schooltag1"
        ][0],
        partition_key="f",
    )


def test_asset_schoolmint_grow_generic_tags_tags():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_tags"
        ][0],
        partition_key="t",
    )


def test_asset_schoolmint_grow_generic_tags_usertag1():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_usertag1"
        ][0],
        partition_key="t",
    )


def test_asset_schoolmint_grow_generic_tags_usertypes():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "generic_tags_usertypes"
        ][0],
        partition_key="f",
    )


def test_asset_schoolmint_grow_informals():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "informals"
        ][0],
    )


def test_asset_schoolmint_grow_measurements():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "measurements"
        ][0],
    )


def test_asset_schoolmint_grow_meetings():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "meetings"
        ][0],
    )


def test_asset_schoolmint_grow_roles():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "roles"
        ][0],
    )


def test_asset_schoolmint_grow_rubrics():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "rubrics"
        ][0],
    )


def test_asset_schoolmint_grow_schools():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "schools"
        ][0],
    )


def test_asset_schoolmint_grow_users():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "users"
        ][0],
        partition_key="f",
    )


def test_asset_schoolmint_grow_videos():
    _test_asset(
        asset=[
            a
            for a in schoolmint_grow_static_partition_assets
            if a.key.path[-1] == "videos"
        ][0],
    )


def test_asset_schoolmint_grow_observations():
    _test_asset(asset=observations)


def test_asset_schoolmint_grow_assignments():
    _test_asset(asset=assignments, partition_key="f|2024-09-16")
