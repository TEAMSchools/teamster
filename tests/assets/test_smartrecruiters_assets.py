from dagster import materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.resources import SMARTRECRUITERS_RESOURCE
from teamster.kipptaf.smartrecruiters.assets import smartrecruiters_report_assets


def _test_asset(assets, asset_name):
    asset = [a for a in assets if a.key.path[-1] == asset_name][0]

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
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""


def test_asset_smartrecruiters_applicants():
    _test_asset(assets=smartrecruiters_report_assets, asset_name="applicants")


def test_asset_smartrecruiters_applications():
    _test_asset(assets=smartrecruiters_report_assets, asset_name="applications")
