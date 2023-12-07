from dagster import EnvVar, materialize
from dagster_gcp import GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.kipptaf.smartrecruiters.assets import build_smartrecruiters_report_asset
from teamster.kipptaf.smartrecruiters.resources import SmartRecruitersResource


def _test_asset(asset_name, report_id):
    asset = build_smartrecruiters_report_asset(
        asset_name=asset_name, code_location="staging", report_id=report_id
    )

    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_avro": GCSIOManager(
                gcs=GCSResource(project=GCS_PROJECT_NAME),
                gcs_bucket="teamster-staging",
                object_type="avro",
            ),
            "smartrecruiters": SmartRecruitersResource(
                smart_token=EnvVar("SMARTRECRUITERS_SMARTTOKEN")
            ),
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]
        .value
        > 0
    )


def test_asset_smartrecruiters_applicants():
    _test_asset(
        asset_name="applicants", report_id="e841aa3f-b037-4976-b75f-8ef43e177a45"
    )


def test_asset_smartrecruiters_applications():
    _test_asset(
        asset_name="applications", report_id="878d114e-8e48-4ffe-a81b-cb3c92ee653f"
    )
