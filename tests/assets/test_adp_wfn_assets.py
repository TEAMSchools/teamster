import random

from dagster import PartitionsDefinition, TextMetadataValue, materialize
from dagster._core.events import StepMaterializationData
from dagster_shared import check

from teamster.code_locations.kipptaf.adp.workforce_now.api.assets import workers
from teamster.code_locations.kipptaf.resources import ADP_WORKFORCE_NOW_RESOURCE
from teamster.core.resources import get_io_manager_gcs_avro


def test_workers():
    partitions_def = check.inst(obj=workers.partitions_def, ttype=PartitionsDefinition)
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
