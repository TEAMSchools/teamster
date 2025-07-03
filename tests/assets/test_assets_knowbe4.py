from dagster import TextMetadataValue, materialize
from dagster._core.events import StepMaterializationData
from dagster_shared import check

from teamster.core.resources import get_io_manager_gcs_avro


def _test_asset(selection):
    from teamster.code_locations.kipptaf.knowbe4.assets import assets as KNOWBE4_ASSETS
    from teamster.code_locations.kipptaf.resources import KNOWBE4_RESOURCE

    result = materialize(
        assets=KNOWBE4_ASSETS,
        selection=selection,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "knowbe4": KNOWBE4_RESOURCE,
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

    extras = check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )
    assert extras.text == ""


def test_asset_knowbe4_training_enrollments():
    _test_asset("kipptaf/knowbe4/training/enrollments")
