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
from teamster.core.resources import BIGQUERY_RESOURCE, get_io_manager_gcs_avro


def _test_asset(asset: AssetsDefinition, partition_key: str | None = None):
    if partition_key is not None:
        pass
    else:
        partitions_def = _check.inst(
            obj=asset.partitions_def, ttype=PartitionsDefinition
        )
        partition_keys = partitions_def.get_partition_keys()
        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
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


def test_outlier_detection():
    _test_asset(asset=outlier_detection, partition_key="2024|PM1")
