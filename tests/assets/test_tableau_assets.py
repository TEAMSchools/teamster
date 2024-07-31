import random

from dagster import TextMetadataValue, _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kipptaf.resources import TABLEAU_SERVER_RESOURCE
from teamster.code_locations.kipptaf.tableau.assets import workbook
from teamster.libraries.core.resources import get_io_manager_gcs_avro


def test_workbook():
    partitions_def = _check.not_none(value=workbook.partitions_def)

    partition_keys = partitions_def.get_partition_keys()

    result = materialize(
        assets=[workbook],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "tableau": TABLEAU_SERVER_RESOURCE,
        },
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
    )

    assert result.success
    asset_materialization_event = result.get_asset_materialization_events()[0]
    extras = _check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )

    event_specific_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = _check.inst(
        event_specific_data.materialization.metadata["records"].value, int
    )

    assert records > 0
    assert extras.text == ""
