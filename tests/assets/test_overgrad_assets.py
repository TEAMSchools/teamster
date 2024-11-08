from dagster import (
    AssetsDefinition,
    DynamicPartitionsDefinition,
    EnvVar,
    _check,
    instance_for_test,
    materialize,
)
from dagster._core.events import StepMaterializationData

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.libraries.overgrad.resources import OvergradResource


def _test_asset(
    asset: AssetsDefinition, code_location: str, partition_key=None, instance=None
):
    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        instance=instance,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "overgrad": OvergradResource(
                api_key=EnvVar(f"OVERGRAD_API_KEY_{code_location}"), page_limit=100
            ),
        },
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]

    event_specific_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = _check.inst(
        event_specific_data.materialization.metadata["record_count"].value, int
    )

    assert records > 0

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_schools_kippcamden():
    from teamster.code_locations.kippcamden.overgrad.assets import schools

    _test_asset(asset=schools, code_location="KIPPCAMDEN")


def test_admissions_kippcamden():
    from teamster.code_locations.kippcamden.overgrad.assets import admissions

    _test_asset(asset=admissions, code_location="KIPPCAMDEN")


def test_custom_fields_kippcamden():
    from teamster.code_locations.kippcamden.overgrad.assets import custom_fields

    _test_asset(asset=custom_fields, code_location="KIPPCAMDEN")


def test_followings_kippcamden():
    from teamster.code_locations.kippcamden.overgrad.assets import followings

    _test_asset(asset=followings, code_location="KIPPCAMDEN")


def test_students_kippcamden():
    from teamster.code_locations.kippcamden.overgrad.assets import students

    _test_asset(asset=students, code_location="KIPPCAMDEN")


def test_schools_kippnewark():
    from teamster.code_locations.kippnewark.overgrad.assets import schools

    _test_asset(asset=schools, code_location="KIPPNEWARK")


def test_admissions_kippnewark():
    from teamster.code_locations.kippnewark.overgrad.assets import admissions

    _test_asset(asset=admissions, code_location="KIPPNEWARK")


def test_custom_fields_kippnewark():
    from teamster.code_locations.kippnewark.overgrad.assets import custom_fields

    _test_asset(asset=custom_fields, code_location="KIPPNEWARK")


def test_followings_kippnewark():
    from teamster.code_locations.kippnewark.overgrad.assets import followings

    _test_asset(asset=followings, code_location="KIPPNEWARK")


def test_students_kippnewark():
    from teamster.code_locations.kippnewark.overgrad.assets import students

    _test_asset(asset=students, code_location="KIPPNEWARK")


def test_universities_kipptaf():
    from teamster.code_locations.kipptaf.overgrad.assets import universities

    partition_key = "4372"
    partitions_def = _check.inst(
        obj=universities.partitions_def, ttype=DynamicPartitionsDefinition
    )

    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=_check.not_none(value=partitions_def.name),
            partition_keys=[partition_key],
        )

        _test_asset(
            asset=universities,
            code_location="KIPPNEWARK",
            partition_key=partition_key,
            instance=instance,
        )
