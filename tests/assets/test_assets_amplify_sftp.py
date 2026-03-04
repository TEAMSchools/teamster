import random

from dagster import AssetsDefinition, EnvVar, materialize


def _test_asset(
    code_location: str,
    asset: AssetsDefinition,
    partition_key: str | None = None,
    instance=None,
):
    from teamster.core.resources import get_io_manager_gcs_avro
    from teamster.libraries.ssh.resources import SSHResource

    SSH_RESOURCE_AMPLIFY = SSHResource(
        remote_host=EnvVar("AMPLIFY_SFTP_HOST"),
        remote_port=22,
        username=EnvVar(f"AMPLIFY_SFTP_USERNAME_{code_location.upper()}"),
        password=EnvVar(f"AMPLIFY_SFTP_PASSWORD_{code_location.upper()}"),
    )

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
    from teamster.code_locations.kippnewark.amplify.mclass.sftp.assets import (
        benchmark_student_summary,
    )

    _test_asset(code_location="kipptaf", asset=benchmark_student_summary)


def test_amplify_mclass_pm_student_summary_kipptaf():
    from teamster.code_locations.kippnewark.amplify.mclass.sftp.assets import (
        pm_student_summary,
    )

    _test_asset(code_location="kipptaf", asset=pm_student_summary)


def test_amplify_mclass_benchmark_student_summary_kipppaterson():
    from teamster.code_locations.kipppaterson.amplify.mclass.sftp.assets import (
        benchmark_student_summary,
    )

    _test_asset(code_location="kipppaterson", asset=benchmark_student_summary)


def test_amplify_mclass_pm_student_summary_kipppaterson():
    from teamster.code_locations.kipppaterson.amplify.mclass.sftp.assets import (
        pm_student_summary,
    )

    _test_asset(code_location="kipppaterson", asset=pm_student_summary)
