"""Offline tests for the cursor-paged Overgrad list pull and its dedupe."""

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


def test_merge_keeps_newer_copy():
    assert merge_by_id([_rec(1, T10), _rec(1, T11)]) == [_rec(1, T11)]


def test_merge_keeps_newer_copy_seen_first():
    assert merge_by_id([_rec(1, T11), _rec(1, T10)]) == [_rec(1, T11)]


def test_merge_keeps_distinct_ids():
    assert sorted(r["id"] for r in merge_by_id([_rec(1, T10), _rec(2, T11)])) == [1, 2]


def test_merge_none_updated_at_loses():
    assert merge_by_id([_rec(1, None), _rec(1, T10)]) == [_rec(1, T10)]


def test_merge_naive_updated_at_treated_as_utc():
    merged = merge_by_id([_rec(1, "2026-10-28T10:00:00.000"), _rec(1, T11)])

    assert merged == [_rec(1, T11)]


def test_merge_keeps_records_without_id():
    no_id = {"updated_at": T10}

    assert merge_by_id([no_id, _rec(1, T10), no_id]) == [_rec(1, T10), no_id, no_id]


_calls: list[str] = []


class _FakeOvergrad(OvergradResource):
    # before `list`, whose name shadows the builtin for later annotations
    def list_by_cursor(self, path: str) -> list[dict]:
        _calls.append("list_by_cursor")

        # a cursor pull repeats boundary records and records edited mid-pull
        return [
            {"id": 1, "updated_at": T10, "university": {"id": 99}},
            {"id": 2, "updated_at": T10, "university": {"id": 99}},
            {"id": 1, "updated_at": T11, "university": {"id": 99}},
        ]

    def list(self, path: str, *args: str, **kwargs) -> list[dict]:
        _calls.append("list")
        return []


def _materialize(name: str, schema):
    _calls.clear()

    return materialize(
        assets=[build_overgrad_asset(code_location="test", name=name, schema=schema)],
        resources={
            "io_manager_gcs_avro": mem_io_manager,
            "overgrad": _FakeOvergrad(api_key="test"),
        },
    )


def test_cursor_endpoint_dedupes_by_id():
    result = _materialize("followings", FOLLOWING_SCHEMA)

    assert _calls == ["list_by_cursor"]

    [mat] = result.asset_materializations_for_node("test__overgrad__followings")
    assert mat.metadata["record_count"].value == 2


def test_other_endpoints_page_by_number():
    _materialize("custom_fields", CUSTOM_FIELD_SCHEMA)

    assert _calls == ["list"]
