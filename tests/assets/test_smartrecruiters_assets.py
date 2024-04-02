from dagster import materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.resources import SMARTRECRUITERS_RESOURCE
from teamster.kipptaf.smartrecruiters.assets import build_smartrecruiters_report_asset


def _test_asset(asset_name, report_id):
    asset = build_smartrecruiters_report_asset(
        asset_name=asset_name, code_location="staging", report_id=report_id
    )

    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "smartrecruiters": SMARTRECRUITERS_RESOURCE,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]  # type: ignore
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
