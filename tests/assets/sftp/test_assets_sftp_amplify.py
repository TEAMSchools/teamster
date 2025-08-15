import random

from dagster import AssetsDefinition, materialize


def _test_asset(
    asset: AssetsDefinition, partition_key: str | None = None, instance=None
):
    from teamster.code_locations.kipptaf.resources import SSH_RESOURCE_AMPLIFY
    from teamster.core.resources import get_io_manager_gcs_avro

    if partition_key is None and asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        instance=instance,
        partition_key=partition_key,
        resources={
            "ssh_amplify": SSH_RESOURCE_AMPLIFY,
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
        },
    )

    assert result.success

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_amplify_mclass_benchmark_student_summary_kipptaf():
    from teamster.code_locations.kipptaf.amplify.mclass.sftp.assets import (
        benchmark_student_summary,
    )

    _test_asset(asset=benchmark_student_summary)


def test_amplify_mclass_pm_student_summary_kipptaf():
    from teamster.code_locations.kipptaf.amplify.mclass.sftp.assets import (
        pm_student_summary,
    )

    _test_asset(asset=pm_student_summary)
