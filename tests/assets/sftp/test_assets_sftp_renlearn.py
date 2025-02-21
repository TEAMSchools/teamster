import random

from dagster import materialize

from teamster.core.resources import get_io_manager_gcs_avro
from tests.utils import get_renlearn_ssh_resource


def _test_asset(asset, ssh_resource: dict, partition_key=None, instance=None):
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
            **ssh_resource,
        },
    )

    assert result.success

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_renlearn_accelerated_reader_kippnj():
    from teamster.code_locations.kippnewark.renlearn.assets import accelerated_reader

    _test_asset(
        asset=accelerated_reader,
        ssh_resource={"ssh_renlearn": get_renlearn_ssh_resource("kippnj")},
    )


def test_renlearn_accelerated_reader_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import accelerated_reader

    _test_asset(
        asset=accelerated_reader,
        ssh_resource={"ssh_renlearn": get_renlearn_ssh_resource("kippmiami")},
    )


def test_renlearn_star_kippnj():
    from teamster.code_locations.kippnewark.renlearn.assets import star

    _test_asset(
        asset=star, ssh_resource={"ssh_renlearn": get_renlearn_ssh_resource("kippnj")}
    )


def test_renlearn_star_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import star

    _test_asset(
        asset=star,
        ssh_resource={"ssh_renlearn": get_renlearn_ssh_resource("kippmiami")},
    )


def test_renlearn_star_skill_area_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import star_skill_area

    _test_asset(
        asset=star_skill_area,
        ssh_resource={"ssh_renlearn": get_renlearn_ssh_resource("kippmiami")},
    )


def test_renlearn_star_dashboard_standards_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import (
        star_dashboard_standards,
    )

    _test_asset(
        asset=star_dashboard_standards,
        ssh_resource={"ssh_renlearn": get_renlearn_ssh_resource("kippmiami")},
    )


def test_renlearn_fast_star_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import fast_star

    _test_asset(
        asset=fast_star,
        ssh_resource={"ssh_renlearn": get_renlearn_ssh_resource("kippmiami")},
        partition_key="2024-07-01|SR",
    )
