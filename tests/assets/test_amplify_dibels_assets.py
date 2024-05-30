from dagster import materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.amplify.dibels.assets import data_farming
from teamster.kipptaf.resources import DIBELS_DATA_SYSTEM_RESOURCE


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
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["row_count"]
        .value
        > 0
    )
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""
