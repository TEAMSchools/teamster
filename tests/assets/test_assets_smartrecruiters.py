from types import SimpleNamespace

from dagster import materialize, mem_io_manager
from dagster._core.events import StepMaterializationData
from dagster_shared import check
from requests.exceptions import HTTPError

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.libraries.smartrecruiters.assets import (
    build_smartrecruiters_report_asset,
)
from teamster.libraries.smartrecruiters.resources import SmartRecruitersResource

PENDING_400 = (
    '{"message":"Report has been already generated or is pending generation."}'
)


def _materialize_offline(monkeypatch, post_error: str, file_pages: list[list[dict]]):
    """Materialize a report asset whose POST fails with `post_error`.

    `file_pages` are successive GET .../files responses; the download returns
    one CSV row.
    """
    gets = []

    def post(self, endpoint, *args, **kwargs):
        raise HTTPError(post_error)

    def get(self, endpoint, *args, **kwargs):
        gets.append(endpoint)
        if endpoint.endswith("/recent/data"):
            return SimpleNamespace(text="Application ID\nA1\n")
        page = file_pages.pop(0)
        return SimpleNamespace(json=lambda: {"content": page})

    monkeypatch.setattr(SmartRecruitersResource, "post", post)
    monkeypatch.setattr(SmartRecruitersResource, "get", get)

    asset = build_smartrecruiters_report_asset(
        asset_key=["test", "smartrecruiters", "applications"],
        report_id="r1",
        schema={"fields": [{"name": "application_id"}]},
    )

    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_avro": mem_io_manager,
            "smartrecruiters": SmartRecruitersResource(smart_token="x"),
        },
        raise_on_error=False,
    )

    return result, gets


def test_pending_report_waits_on_in_flight_file(monkeypatch):
    result, gets = _materialize_offline(
        monkeypatch,
        post_error=PENDING_400,
        file_pages=[
            [
                {"reportFileId": "f2", "reportFileStatus": "RUNNING"},
                {"reportFileId": "f1", "reportFileStatus": "COMPLETED"},
            ],
            [
                {"reportFileId": "f2", "reportFileStatus": "COMPLETED"},
                {"reportFileId": "f1", "reportFileStatus": "COMPLETED"},
            ],
        ],
    )

    assert result.success
    assert gets[-1].endswith("/recent/data")
    assert len(gets) == 3


def test_pending_report_downloads_completed_file(monkeypatch):
    result, gets = _materialize_offline(
        monkeypatch,
        post_error=PENDING_400,
        file_pages=[[{"reportFileId": "f2", "reportFileStatus": "COMPLETED"}]],
    )

    assert result.success
    assert len(gets) == 2


def test_other_post_error_still_fails(monkeypatch):
    result, gets = _materialize_offline(
        monkeypatch, post_error='{"message":"Report not found."}', file_pages=[]
    )

    assert not result.success
    assert gets == []


def _test_asset(asset):
    from teamster.code_locations.kipptaf.resources import SMARTRECRUITERS_RESOURCE

    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "smartrecruiters": SMARTRECRUITERS_RESOURCE,
        },
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]
    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    step_materialization_data = check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = check.inst(
        step_materialization_data.materialization.metadata["records"].value, int
    )

    assert records > 0

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_asset_smartrecruiters_applications():
    from teamster.code_locations.kipptaf.smartrecruiters.assets import applications

    _test_asset(applications)
