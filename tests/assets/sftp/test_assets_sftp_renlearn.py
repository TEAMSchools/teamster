import random

from dagster import AssetsDefinition, materialize


def _test_asset(
    asset: AssetsDefinition,
    code_location: str,
    partition_key: str | None = None,
    instance=None,
):
    from teamster.core.resources import get_io_manager_gcs_avro
    from tests.utils import get_renlearn_ssh_resource

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
            "ssh_renlearn": get_renlearn_ssh_resource(code_location),
        },
    )

    assert result.success

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_renlearn_star_kippnj():
    from teamster.code_locations.kippnewark.renlearn.assets import star

    _test_asset(asset=star, code_location="kippnj")


def test_renlearn_star_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import star

    _test_asset(asset=star, code_location="kippmiami")


def test_renlearn_star_skill_area_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import star_skill_area

    _test_asset(asset=star_skill_area, code_location="kippmiami")


def test_renlearn_star_dashboard_standards_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import (
        star_dashboard_standards,
    )

    _test_asset(asset=star_dashboard_standards, code_location="kippmiami")


def test_renlearn_fast_star_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import fast_star

    _test_asset(asset=fast_star, code_location="kippmiami")
