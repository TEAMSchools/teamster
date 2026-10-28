"""Offline tests for the catch-up pull that follows a full Overgrad list pull."""

import re
from datetime import UTC, datetime, timedelta

from dagster import materialize, mem_io_manager

from teamster.code_locations.kippnewark.overgrad.schema import (
    CUSTOM_FIELD_SCHEMA,
    FOLLOWING_SCHEMA,
)
from teamster.libraries.overgrad.assets import build_overgrad_asset, merge_by_id
from teamster.libraries.overgrad.resources import OvergradResource

T10 = "2026-10-28T10:00:00.000Z"
T11 = "2026-10-28T11:00:00.000Z"


def _rec(id: int, updated_at: str | None) -> dict:
    return {"id": id, "updated_at": updated_at}


def test_merge_dedupes_within_full_pull():
    assert merge_by_id([_rec(1, T10), _rec(1, T11)], []) == [_rec(1, T11)]


def test_merge_catch_up_newer_wins():
    assert merge_by_id([_rec(1, T10)], [_rec(1, T11)]) == [_rec(1, T11)]


def test_merge_full_newer_wins():
    assert merge_by_id([_rec(1, T11)], [_rec(1, T10)]) == [_rec(1, T11)]


def test_merge_adds_catch_up_only_record():
    merged = merge_by_id([_rec(1, T10)], [_rec(2, T11)])

    assert sorted(r["id"] for r in merged) == [1, 2]


def test_merge_none_updated_at_loses():
    assert merge_by_id([_rec(1, None)], [_rec(1, T10)]) == [_rec(1, T10)]


def test_merge_empty_catch_up():
    full = [_rec(1, T10), _rec(2, T11)]

    assert merge_by_id(full, []) == full


def test_merge_naive_updated_at_treated_as_utc():
    merged = merge_by_id([_rec(1, "2026-10-28T10:00:00.000")], [_rec(1, T11)])

    assert merged == [_rec(1, T11)]


def test_merge_keeps_records_without_id():
    no_id = {"updated_at": T10}

    assert merge_by_id([no_id, _rec(1, T10)], [no_id]) == [_rec(1, T10), no_id, no_id]


class _FakeOvergrad(OvergradResource):
    def list(self, path: str, *args: str, **kwargs) -> list[dict]:
        _calls.append(kwargs.get("params"))

        if len(_calls) == 1:
            return [{"id": 1, "updated_at": T10, "university": {"id": 99}}]

        return [
            {"id": 1, "updated_at": T11, "university": {"id": 99}},
            {"id": 2, "updated_at": T11, "university": {"id": 99}},
        ]


_calls: list[dict | None] = []


def _materialize(name: str, schema):
    _calls.clear()

    return materialize(
        assets=[build_overgrad_asset(code_location="test", name=name, schema=schema)],
        resources={
            "io_manager_gcs_avro": mem_io_manager,
            "overgrad": _FakeOvergrad(api_key="test"),
        },
    )


def test_catch_up_pull_params_and_merge():
    before = datetime.now(UTC)
    result = _materialize("followings", FOLLOWING_SCHEMA)
    after = datetime.now(UTC)

    assert len(_calls) == 2
    assert _calls[0] is None

    updated_after = _calls[1]["updated_after"]  # pyright: ignore[reportOptionalSubscript]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", updated_after)

    parsed = datetime.fromisoformat(updated_after)
    assert (
        before - timedelta(seconds=1, milliseconds=1)
        <= parsed
        <= after - timedelta(seconds=1)
    )

    [mat] = result.asset_materializations_for_node("test__overgrad__followings")
    assert mat.metadata["record_count"].value == 2


def test_no_catch_up_outside_catch_up_endpoints():
    _materialize("custom_fields", CUSTOM_FIELD_SCHEMA)

    assert len(_calls) == 1
