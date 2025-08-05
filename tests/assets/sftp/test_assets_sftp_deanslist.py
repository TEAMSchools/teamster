import random

from dagster import AssetsDefinition, materialize


def _test_asset(
    asset: AssetsDefinition, partition_key: str | None = None, instance=None
):
    from teamster.code_locations.kipptaf.resources import SSH_RESOURCE_DEANSLIST
    from teamster.core.resources import get_io_manager_gcs_avro

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
            "ssh_deanslist": SSH_RESOURCE_DEANSLIST,
        },
    )

    assert result.success

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_deanslist_reconcile_attendance_kipptaf():
    from teamster.code_locations.kipptaf.deanslist.assets import reconcile_attendance

    _test_asset(asset=reconcile_attendance)


def test_deanslist_reconcile_suspensions_kipptaf():
    from teamster.code_locations.kipptaf.deanslist.assets import reconcile_suspensions

    _test_asset(asset=reconcile_suspensions)
