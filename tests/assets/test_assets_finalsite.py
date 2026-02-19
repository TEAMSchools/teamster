from dagster import AssetsDefinition, EnvVar, materialize
from dagster._core.events import StepMaterializationData
from dagster_shared import check

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.libraries.finalsite.resources import FinalsiteResource


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
            "finalsite": FinalsiteResource(
                server=code_location,
                credential_id=EnvVar(
                    f"FINALSITE_CREDENTIAL_ID_{code_location.upper()}"
                ),
                secret=EnvVar(f"FINALSITE_SECRET_{code_location.upper()}"),
            ),
        },
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]

    event_specific_data = check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = check.inst(
        event_specific_data.materialization.metadata["record_count"].value, int
    )

    assert records > 0

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_finalsite_contact_statuses_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.finalsite.assets import contact_statuses

    _test_asset(asset=contact_statuses, code_location=CODE_LOCATION)


def test_finalsite_contacts_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.finalsite.assets import contacts

    _test_asset(asset=contacts, code_location=CODE_LOCATION)


def test_finalsite_fields_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.finalsite.assets import fields

    _test_asset(asset=fields, code_location=CODE_LOCATION)


def test_finalsite_grades_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.finalsite.assets import grades

    _test_asset(asset=grades, code_location=CODE_LOCATION)


def test_finalsite_school_years_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.finalsite.assets import school_years

    _test_asset(asset=school_years, code_location=CODE_LOCATION)


def test_finalsite_users_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.finalsite.assets import users

    _test_asset(asset=users, code_location=CODE_LOCATION)
