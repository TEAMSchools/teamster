from dagster import TextMetadataValue, _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.resources import SMARTRECRUITERS_RESOURCE
from teamster.kipptaf.smartrecruiters.assets import assets


def _test_asset(assets, asset_name):
    asset = [a for a in assets if a.key.path[-1] == asset_name][0]

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


def test_asset_smartrecruiters_applicants():
    _test_asset(assets=assets, asset_name="applicants")


def test_asset_smartrecruiters_applications():
    _test_asset(assets=assets, asset_name="applications")
