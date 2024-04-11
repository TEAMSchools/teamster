import random

from dagster import AssetsDefinition, materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.google.directory.assets import (
    groups,
    members,
    orgunits,
    role_assignments,
    roles,
    users,
)
from teamster.kipptaf.resources import GOOGLE_DIRECTORY_RESOURCE


def _test_asset(asset: AssetsDefinition):
    if asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    else:
        partition_key = None

    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "google_directory": GOOGLE_DIRECTORY_RESOURCE,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["record_count"]
        .value
        > 0
    )


def test_asset_google_directory_groups():
    _test_asset(groups)


def test_asset_google_directory_members():
    _test_asset(members)


def test_asset_google_directory_orgunits():
    _test_asset(orgunits)


def test_asset_google_directory_role_assignments():
    _test_asset(role_assignments)


def test_asset_google_directory_roles():
    _test_asset(roles)


def test_asset_google_directory_users():
    _test_asset(users)
