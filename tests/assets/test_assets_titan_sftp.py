import random

from dagster import AssetsDefinition, materialize


def _test_asset(
    asset: AssetsDefinition,
    code_location: str,
    partition_key: str | None = None,
    instance=None,
):
    from teamster.core.resources import get_io_manager_gcs_avro
    from tests.utils import get_titan_ssh_resource

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
            "ssh_titan": get_titan_ssh_resource(code_location),
        },
    )

    assert result.success

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_titan_person_data_kippnewark():
    from teamster.code_locations.kippnewark.titan.assets import person_data

    _test_asset(asset=person_data, code_location="kippnewark")


def test_titan_person_data_kippcamden():
    from teamster.code_locations.kippcamden.titan.assets import person_data

    _test_asset(asset=person_data, code_location="kippcamden")
