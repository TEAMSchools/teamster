import random

from dagster import AssetsDefinition, materialize


def _test_asset(
    asset: AssetsDefinition, partition_key: str | None = None, instance=None
):
    from teamster.core.resources import SSH_IREADY, get_io_manager_gcs_avro

    if partition_key is None and asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys(
            dynamic_partitions_store=instance
        )

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

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

    _test_asset(asset=diagnostic_results)


def test_iready_diagnostic_results_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import diagnostic_results

    _test_asset(asset=diagnostic_results)


def test_iready_personalized_instruction_by_lesson_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import instruction_by_lesson

    _test_asset(asset=instruction_by_lesson)


def test_iready_personalized_instruction_by_lesson_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import instruction_by_lesson

    _test_asset(asset=instruction_by_lesson)


def test_iready_instructional_usage_data_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import instructional_usage_data

    _test_asset(asset=instructional_usage_data)


def test_iready_instructional_usage_data_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import (
        instructional_usage_data,
    )

    _test_asset(asset=instructional_usage_data)


def test_iready_diagnostic_and_instruction_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import (
        diagnostic_and_instruction,
    )

    _test_asset(asset=diagnostic_and_instruction)


def test_iready_diagnostic_and_instruction_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import (
        diagnostic_and_instruction,
    )

    _test_asset(asset=diagnostic_and_instruction)


def test_iready_instruction_by_lesson_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import instruction_by_lesson

    _test_asset(asset=instruction_by_lesson)


def test_iready_instruction_by_lesson_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import instruction_by_lesson

    _test_asset(asset=instruction_by_lesson)


def test_iready_instruction_by_lesson_pro_kippnewark():
    from teamster.code_locations.kippnewark.iready.assets import (
        instruction_by_lesson_pro,
    )

    _test_asset(asset=instruction_by_lesson_pro)


def test_iready_instruction_by_lesson_pro_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import (
        instruction_by_lesson_pro,
    )

    _test_asset(asset=instruction_by_lesson_pro)
