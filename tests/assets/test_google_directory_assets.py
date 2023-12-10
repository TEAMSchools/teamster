import random

from dagster import AssetsDefinition, materialize
from dagster_gcp import GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.kipptaf.google.directory.assets import (
    groups,
    members,
    orgunits,
    role_assignments,
    roles,
    users,
)
from teamster.kipptaf.google.resources import GoogleDirectoryResource


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
            "io_manager_gcs_avro": GCSIOManager(
                gcs=GCSResource(project=GCS_PROJECT_NAME),
                gcs_bucket="teamster-staging",
                object_type="avro",
            ),
            "google_directory": GoogleDirectoryResource(
                customer_id="C029u7m0n",
                service_account_file_path="/etc/secret-volume/gcloud_service_account_json",
                delegated_account="dagster@apps.teamschools.org",
            ),
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
