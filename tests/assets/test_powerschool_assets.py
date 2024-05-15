import random

from dagster import materialize

from teamster.core.resources import (
    DB_POWERSCHOOL,
    SSH_POWERSCHOOL,
    get_io_manager_gcs_file,
)


def _test_asset(assets, asset_name):
    asset = [a for a in assets if a.key.path[-1] == asset_name][0]

    if asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    else:
        partition_key = None

    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        resources={
            "io_manager_gcs_file": get_io_manager_gcs_file("staging"),
            "ssh_powerschool": SSH_POWERSCHOOL,
            "db_powerschool": DB_POWERSCHOOL,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]  # type: ignore
        .value
        > 0
    )


def test_schools_kippnewark():
    from teamster.kippnewark.powerschool import assets

    _test_asset(assets=assets, asset_name="schools")
