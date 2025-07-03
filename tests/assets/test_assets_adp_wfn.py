import random

from dagster import PartitionsDefinition, TextMetadataValue, materialize
from dagster_shared import check


def _test(partition_key: str | None = None):
    from teamster.code_locations.kipptaf.adp.workforce_now.api.assets import (
        adp_workforce_now_workers,
    )
    from teamster.code_locations.kipptaf.resources import ADP_WORKFORCE_NOW_RESOURCE
    from teamster.core.resources import get_io_manager_gcs_avro

    if partition_key is None:
        partitions_def = check.inst(
            obj=adp_workforce_now_workers.partitions_def, ttype=PartitionsDefinition
        )

        partition_keys = partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[adp_workforce_now_workers],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "adp_wfn": ADP_WORKFORCE_NOW_RESOURCE,
        },
        partition_key=partition_key,
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]

    records = check.inst(
        asset_materialization_event.materialization.metadata["record_count"].value, int
    )
    assert records > 0

    extras = check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )
    assert extras.text == ""


def test_workers():
    _test(partition_key="07/01/2025")
