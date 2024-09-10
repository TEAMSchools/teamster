import random

from dagster import materialize

from teamster.core.resources import SSH_IREADY, get_io_manager_gcs_avro


def _test_asset(asset, partition_key=None, instance=None):
    if partition_key is not None:
        pass
    elif asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys(
            dynamic_partitions_store=instance
        )

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    else:
        partition_key = None

    result = materialize(
        assets=[asset],
        instance=instance,
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "ssh_iready": SSH_IREADY,
        },
    )

    assert result.success

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_iready_diagnostic_results_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import diagnostic_results

    _test_asset(asset=diagnostic_results, partition_key="2024|ela")


def test_iready_diagnostic_results_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import diagnostic_results

    _test_asset(asset=diagnostic_results, partition_key="2024|ela")


def test_iready_personalized_instruction_by_lesson_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import (
        personalized_instruction_by_lesson,
    )

    _test_asset(asset=personalized_instruction_by_lesson, partition_key="2024|ela")


def test_iready_personalized_instruction_by_lesson_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import (
        personalized_instruction_by_lesson,
    )

    _test_asset(asset=personalized_instruction_by_lesson, partition_key="2024|ela")


def test_iready_instructional_usage_data_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import instructional_usage_data

    _test_asset(asset=instructional_usage_data, partition_key="2024|ela")


def test_iready_instructional_usage_data_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import (
        instructional_usage_data,
    )

    _test_asset(asset=instructional_usage_data, partition_key="2024|ela")


def test_iready_diagnostic_and_instruction_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import (
        diagnostic_and_instruction,
    )

    _test_asset(asset=diagnostic_and_instruction, partition_key="2024|ela")


def test_iready_diagnostic_and_instruction_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import (
        diagnostic_and_instruction,
    )

    _test_asset(asset=diagnostic_and_instruction, partition_key="2021|math")


def test_iready_instruction_by_lesson_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import instruction_by_lesson

    _test_asset(asset=instruction_by_lesson)


def test_iready_instruction_by_lesson_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import instruction_by_lesson

    _test_asset(asset=instruction_by_lesson, partition_key="2024|ela")
