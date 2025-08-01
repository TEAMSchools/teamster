from dagster import materialize
from dagster._core.events import StepMaterializationData
from dagster_shared import check

from teamster.core.resources import get_io_manager_gcs_avro


def _test_asset(asset):
    from teamster.code_locations.kipptaf.resources import SMARTRECRUITERS_RESOURCE

    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "smartrecruiters": SMARTRECRUITERS_RESOURCE,
        },
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]
    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    step_materialization_data = check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = check.inst(
        step_materialization_data.materialization.metadata["records"].value, int
    )

    assert records > 0

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_asset_smartrecruiters_applicants():
    from teamster.code_locations.kipptaf.smartrecruiters.assets import applicants

    _test_asset(applicants)


def test_asset_smartrecruiters_applications():
    from teamster.code_locations.kipptaf.smartrecruiters.assets import applications

    _test_asset(applications)
