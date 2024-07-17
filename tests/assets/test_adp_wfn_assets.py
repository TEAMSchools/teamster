import random

from dagster import PartitionsDefinition, TextMetadataValue, _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kipptaf.adp.workforce_now.api.assets import workers
from teamster.code_locations.kipptaf.resources import ADP_WORKFORCE_NOW_RESOURCE
from teamster.libraries.core.resources import get_io_manager_gcs_avro


def test_workers():
    partitions_def = _check.inst(obj=workers.partitions_def, ttype=PartitionsDefinition)
    partition_keys = partitions_def.get_partition_keys()

    result = materialize(
        assets=[workers],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "adp_wfn": ADP_WORKFORCE_NOW_RESOURCE,
        },
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
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
