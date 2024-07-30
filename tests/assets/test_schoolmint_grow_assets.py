import random

from dagster import TextMetadataValue, _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kipptaf.resources import SCHOOLMINT_GROW_RESOURCE
from teamster.code_locations.kipptaf.schoolmint.grow.assets import assets
from teamster.libraries.core.resources import get_io_manager_gcs_avro


def _test_asset(assets, asset_name, partition_key=None):
    asset = [a for a in assets if a.key.path[-1] == asset_name][0]

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
        assets=assets, asset_name="generic_tags_assignmentpresets", partition_key="f"
    )


def test_asset_schoolmint_grow_generic_tags_courses():
    _test_asset(assets=assets, asset_name="generic_tags_courses", partition_key="f")


def test_asset_schoolmint_grow_generic_tags_eventtag1():
    _test_asset(assets=assets, asset_name="generic_tags_eventtag1", partition_key="t")


def test_asset_schoolmint_grow_generic_tags_goaltypes():
    _test_asset(assets=assets, asset_name="generic_tags_goaltypes", partition_key="f")


def test_asset_schoolmint_grow_generic_tags_grades():
    _test_asset(assets=assets, asset_name="generic_tags_grades", partition_key="f")


def test_asset_schoolmint_grow_generic_tags_measurementgroups():
    _test_asset(
        assets=assets, asset_name="generic_tags_measurementgroups", partition_key="f"
    )


def test_asset_schoolmint_grow_generic_tags_meetingtypes():
    _test_asset(
        assets=assets, asset_name="generic_tags_meetingtypes", partition_key="f"
    )


def test_asset_schoolmint_grow_generic_tags_observationtypes():
    _test_asset(
        assets=assets, asset_name="generic_tags_observationtypes", partition_key="f"
    )


def test_asset_schoolmint_grow_generic_tags_rubrictag1():
    _test_asset(assets=assets, asset_name="generic_tags_rubrictag1", partition_key="f")


def test_asset_schoolmint_grow_generic_tags_schooltag1():
    _test_asset(assets=assets, asset_name="generic_tags_schooltag1", partition_key="f")


def test_asset_schoolmint_grow_generic_tags_tags():
    _test_asset(assets=assets, asset_name="generic_tags_tags", partition_key="t")


def test_asset_schoolmint_grow_generic_tags_usertag1():
    _test_asset(assets=assets, asset_name="generic_tags_usertag1", partition_key="t")


def test_asset_schoolmint_grow_generic_tags_usertypes():
    _test_asset(assets=assets, asset_name="generic_tags_usertypes", partition_key="f")


def test_asset_schoolmint_grow_informals():
    _test_asset(assets=assets, asset_name="informals")


def test_asset_schoolmint_grow_measurements():
    _test_asset(assets=assets, asset_name="measurements")


def test_asset_schoolmint_grow_meetings():
    _test_asset(assets=assets, asset_name="meetings")


def test_asset_schoolmint_grow_roles():
    _test_asset(assets=assets, asset_name="roles")


def test_asset_schoolmint_grow_rubrics():
    _test_asset(assets=assets, asset_name="rubrics")


def test_asset_schoolmint_grow_schools():
    _test_asset(assets=assets, asset_name="schools")


def test_asset_schoolmint_grow_users():
    _test_asset(assets=assets, asset_name="users")


def test_asset_schoolmint_grow_videos():
    _test_asset(assets=assets, asset_name="videos")


def test_asset_schoolmint_grow_observations():
    _test_asset(assets=assets, asset_name="observations")


def test_asset_schoolmint_grow_assignments():
    _test_asset(assets=assets, asset_name="assignments")
