"""Offline test: a failed university-partition registration must not fail the asset."""

from dagster import DagsterInstance, materialize, mem_io_manager
from requests.exceptions import ReadTimeout

from teamster.code_locations.kippnewark.overgrad.schema import FOLLOWING_SCHEMA
from teamster.libraries.overgrad.assets import build_overgrad_asset
from teamster.libraries.overgrad.resources import OvergradResource


class _FakeOvergrad(OvergradResource):
    def list_by_cursor(self, path: str) -> list[dict]:
        return [{"id": 1, "university": {"id": 99}}]


def test_followings_survives_add_dynamic_partitions_failure(monkeypatch):
    calls = []

    def raise_timeout(*_, **__):
        calls.append(1)
        raise ReadTimeout("Read timed out.")

    monkeypatch.setattr(DagsterInstance, "add_dynamic_partitions", raise_timeout)

    asset = build_overgrad_asset(
        code_location="test", name="followings", schema=FOLLOWING_SCHEMA
    )

    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_avro": mem_io_manager,
            "overgrad": _FakeOvergrad(api_key="test"),
        },
        raise_on_error=False,
    )

    assert calls
    assert result.success
