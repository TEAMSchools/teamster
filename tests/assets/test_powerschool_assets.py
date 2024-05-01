import random

from dagster import materialize

from teamster.core.resources import (
    DB_POWERSCHOOL,
    get_io_manager_gcs_file,
    get_ssh_resource_powerschool,
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
            "ssh_powerschool": get_ssh_resource_powerschool(
                "teamacademy.clgpstest.com"
            ),
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
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""
