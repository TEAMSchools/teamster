import random

from dagster import materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.amplify.mclass.assets import (
    benchmark_student_summary,
    pm_student_summary,
)
from teamster.kipptaf.resources import MCLASS_RESOURCE


def _test_asset(asset):
    partition_keys = asset.partitions_def.get_partition_keys()  # type: ignore

    result = materialize(
        assets=[asset],
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "mclass": MCLASS_RESOURCE,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]  # type: ignore
        .value
        > 0
    )
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""  # type: ignore


def test_mclass_asset_benchmark_student_summary():
    _test_asset(benchmark_student_summary)


def test_mclass_asset_pm_student_summary():
    _test_asset(pm_student_summary)
