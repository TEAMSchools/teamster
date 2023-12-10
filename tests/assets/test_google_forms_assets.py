import random

from dagster import AssetsDefinition, materialize
from dagster_gcp import GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.kipptaf.google.forms.assets import form, responses
from teamster.kipptaf.google.resources import GoogleFormsResource


def _test_asset(asset: AssetsDefinition):
    partition_keys = asset.partitions_def.get_partition_keys()

    result = materialize(
        assets=[asset],
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
        resources={
            "io_manager_gcs_avro": GCSIOManager(
                gcs=GCSResource(project=GCS_PROJECT_NAME),
                gcs_bucket="teamster-staging",
                object_type="avro",
            ),
            "google_forms": GoogleFormsResource(
                service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
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


def test_asset_google_forms_form():
    _test_asset(form)


def test_asset_google_forms_responses():
    _test_asset(responses)
