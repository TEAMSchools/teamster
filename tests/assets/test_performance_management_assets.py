import random

from dagster import (
    AssetsDefinition,
    PartitionsDefinition,
    TextMetadataValue,
    _check,
    materialize,
)
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kipptaf.performance_management.assets import (
    outlier_detection,
)
from teamster.libraries.core.resources import BIGQUERY_RESOURCE, get_io_manager_gcs_avro


def test_outlier_detection():
    _check.inst(obj=outlier_detection, ttype=AssetsDefinition)

    partitions_def = _check.inst(
        obj=outlier_detection.partitions_def, ttype=PartitionsDefinition
    )
    partition_keys = partitions_def.get_partition_keys()

    partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[outlier_detection],
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "db_bigquery": BIGQUERY_RESOURCE,
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
