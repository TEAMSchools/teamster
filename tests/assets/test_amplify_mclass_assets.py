import random

from dagster import TextMetadataValue, _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kipptaf.amplify.mclass.assets import (
    benchmark_student_summary,
    pm_student_summary,
)
from teamster.code_locations.kipptaf.resources import MCLASS_RESOURCE
from teamster.libraries.core.resources import get_io_manager_gcs_avro


def _test_asset(asset):
    partition_keys = asset.partitions_def.get_partition_keys()

    result = materialize(
        assets=[asset],
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "mclass": MCLASS_RESOURCE,
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


def test_mclass_asset_benchmark_student_summary():
    _test_asset(benchmark_student_summary)


def test_mclass_asset_pm_student_summary():
    _test_asset(pm_student_summary)
