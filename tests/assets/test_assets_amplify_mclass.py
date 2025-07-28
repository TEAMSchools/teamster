import random

from dagster import (
    AssetsDefinition,
    PartitionsDefinition,
    TextMetadataValue,
    materialize,
)
from dagster._core.events import StepMaterializationData
from dagster_shared import check

from teamster.core.resources import get_io_manager_gcs_avro


def _test_asset(asset: AssetsDefinition, partition_key: str | None = None):
    from teamster.code_locations.kipptaf.resources import MCLASS_RESOURCE

    if partition_key is None:
        partitions_def = check.inst(
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
            "mclass": MCLASS_RESOURCE,
        },
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


def test_mclass_asset_benchmark_student_summary():
    from teamster.code_locations.kipptaf.amplify.mclass.assets import (
        benchmark_student_summary,
    )

    _test_asset(benchmark_student_summary, partition_key="2024-07-01")


def test_mclass_asset_pm_student_summary():
    from teamster.code_locations.kipptaf.amplify.mclass.assets import pm_student_summary

    _test_asset(pm_student_summary, partition_key="2024-07-01")
