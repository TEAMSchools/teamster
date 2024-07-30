from dagster import TextMetadataValue, _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kipptaf.amplify.dibels.assets import data_farming
from teamster.code_locations.kipptaf.resources import DIBELS_DATA_SYSTEM_RESOURCE
from teamster.libraries.core.resources import get_io_manager_gcs_avro


def test_data_farming():
    result = materialize(
        assets=[data_farming],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "dds": DIBELS_DATA_SYSTEM_RESOURCE,
        },
    )

    assert result.success
    asset_materialization_event = result.get_asset_materialization_events()[0]
    event_specific_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )
    records = _check.inst(
        event_specific_data.materialization.metadata["row_count"].value, int
    )
    assert records > 0
    extras = _check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )
    assert extras.text == ""
