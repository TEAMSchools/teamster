import random

from dagster import AssetsDefinition, JsonMetadataValue, TextMetadataValue, materialize
from dagster._core.events import StepMaterializationData
from dagster_shared import check

from teamster.core.resources import get_io_manager_gcs_avro


def _test_asset(
    assets: list[AssetsDefinition], asset_name: str, partition_key: str | None = None
):
    from teamster.code_locations.kipptaf.resources import GROW_RESOURCE

    asset = [a for a in assets if a.key.path[-1] == asset_name][0]

    if partition_key is None:
        partitions_def = check.not_none(value=asset.partitions_def)

        partition_keys = partitions_def.get_partition_keys()

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
        assets=grow_static_partition_assets,
        asset_name="generic_tags_assignmentpresets",
        partition_key="f",
    )


def test_asset_grow_generic_tags_courses():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_courses",
        partition_key="f",
    )


def test_asset_grow_generic_tags_eventtag1():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_eventtag1",
        partition_key="t",
    )


def test_asset_grow_generic_tags_goaltypes():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_goaltypes",
        partition_key="f",
    )


def test_asset_grow_generic_tags_grades():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_grades",
        partition_key="f",
    )


def test_asset_grow_generic_tags_measurementgroups():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_measurementgroups",
        partition_key="f",
    )


def test_asset_grow_generic_tags_meetingtypes():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_meetingtypes",
        partition_key="f",
    )


def test_asset_grow_generic_tags_observationtypes():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_observationtypes",
        partition_key="f",
    )


def test_asset_grow_generic_tags_rubrictag1():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_rubrictag1",
        partition_key="f",
    )


def test_asset_grow_generic_tags_schooltag1():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_schooltag1",
        partition_key="f",
    )


def test_asset_grow_generic_tags_tags():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_tags",
        partition_key="t",
    )


def test_asset_grow_generic_tags_usertag1():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_usertag1",
        partition_key="t",
    )


def test_asset_grow_generic_tags_usertypes():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets,
        asset_name="generic_tags_usertypes",
        partition_key="f",
    )


def test_asset_grow_informals():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(assets=grow_static_partition_assets, asset_name="informals")


def test_asset_grow_measurements():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(assets=grow_static_partition_assets, asset_name="measurements")


def test_asset_grow_meetings():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(assets=grow_static_partition_assets, asset_name="meetings")


def test_asset_grow_roles():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(assets=grow_static_partition_assets, asset_name="roles")


def test_asset_grow_rubrics():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(assets=grow_static_partition_assets, asset_name="rubrics")


def test_asset_grow_schools():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(assets=grow_static_partition_assets, asset_name="schools")


def test_asset_grow_users():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(
        assets=grow_static_partition_assets, asset_name="users", partition_key="f"
    )


def test_asset_grow_videos():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_static_partition_assets,
    )

    _test_asset(assets=grow_static_partition_assets, asset_name="videos")


def test_asset_grow_observations():
    from teamster.code_locations.kipptaf.level_data.grow.assets import observations

    _test_asset(assets=[observations], asset_name="observations")


def test_asset_grow_assignments():
    from teamster.code_locations.kipptaf.level_data.grow.assets import assignments

    _test_asset(
        assets=[assignments], asset_name="assignments", partition_key="f|2024-09-16"
    )


def test_grow_user_sync():
    from teamster.code_locations.kipptaf.level_data.grow.assets import (
        grow_user_sync,
    )
    from teamster.code_locations.kipptaf.resources import GROW_RESOURCE
    from teamster.core.resources import BIGQUERY_RESOURCE

    result = materialize(
        assets=[grow_user_sync],
        resources={"db_bigquery": BIGQUERY_RESOURCE, "grow": GROW_RESOURCE},
    )

    assert result.success

    errors = check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("errors"),
        ttype=JsonMetadataValue,
    )

    assert isinstance(errors.value, list)
    assert len(errors.value) == 0
