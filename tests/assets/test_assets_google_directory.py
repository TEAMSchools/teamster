import random

from dagster import AssetsDefinition, EnvVar, TextMetadataValue, materialize
from dagster._core.events import StepMaterializationData
from dagster_shared import check

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.libraries.google.directory.resources import GoogleDirectoryResource


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
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "google_directory": GoogleDirectoryResource(
                customer_id=EnvVar("GOOGLE_WORKSPACE_CUSTOMER_ID"),
                delegated_account=EnvVar("GOOGLE_DIRECTORY_DELEGATED_ACCOUNT"),
                # service_account_file_path=(
                #     "/etc/secret-volume/gcloud_dagster_service_account.json"
                # ),
            ),
        },
    )

    assert result.success
    asset_materialization_event = result.get_asset_materialization_events()[0]
    event_specific_data = check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )
    records = check.inst(
        event_specific_data.materialization.metadata["record_count"].value, int
    )
    assert records > 0
    extras = check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )
    assert extras.text == ""


def test_asset_google_directory_groups():
    from teamster.code_locations.kipptaf._google.directory.assets import groups

    _test_asset(groups)


def test_asset_google_directory_members():
    from teamster.code_locations.kipptaf._google.directory.assets import members

    _test_asset(members)


def test_asset_google_directory_orgunits():
    from teamster.code_locations.kipptaf._google.directory.assets import orgunits

    _test_asset(orgunits)


def test_asset_google_directory_role_assignments():
    from teamster.code_locations.kipptaf._google.directory.assets import (
        role_assignments,
    )

    _test_asset(role_assignments)


def test_asset_google_directory_roles():
    from teamster.code_locations.kipptaf._google.directory.assets import roles

    _test_asset(roles)


def test_asset_google_directory_users():
    from teamster.code_locations.kipptaf._google.directory.assets import users

    _test_asset(users)
