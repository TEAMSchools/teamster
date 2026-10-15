"""Cube capture with a fake HTTP client. No live calls."""

import datetime as dt
import json
from types import SimpleNamespace

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest registers cube_validate at runtime
from cube_validate import capture_cube, config, snapshot

BUILT = dt.datetime(2026, 10, 15, 19, 5, tzinfo=dt.UTC)


class FakeHttp:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def post(self, url, json, headers):
        self.calls.append((url, json))
        # Cube reads renewQuery from inside the query, so the answer sees that.
        return SimpleNamespace(
            status_code=200, json=lambda: self.answer(url, json["query"])
        )

    def get(self, url, headers):
        return SimpleNamespace(status_code=200, json=lambda: self.answer(url, None))


def _client(answer):
    return capture_cube.CubeClient(
        "https://cube/x", "s", "me@x", http=FakeHttp(answer), sleep=lambda s: None
    )


def _checks():
    return SimpleNamespace(
        cube=config.CubeRows(
            "v", "attendance_date", ("lea_student_identifier", "attendance_date")
        ),
        period_start=dt.date(2026, 10, 5),
    )


def test_row_queries_one_per_day_with_total():
    parts = capture_cube.row_queries(
        _checks(), dt.date(2026, 10, 5), dt.date(2026, 10, 6)
    )
    assert [p for p, _ in parts] == ["2026-10-05", "2026-10-06"]
    q = parts[0][1]
    assert q["ungrouped"] and q["total"] and q["limit"] == 50000
    assert q["filters"][0] == {
        "member": "v.attendance_date",
        "operator": "inDateRange",
        "values": ["2026-10-05", "2026-10-05"],
    }


def test_load_returns_the_answers_own_refresh_and_total():
    c = _client(
        lambda u, q: {
            "data": [{"a": 1}],
            "lastRefreshTime": "2026-10-15T20:00:00.000Z",
            "total": 1,
        }
    )
    r = c.load({"dimensions": []})
    assert (
        r.data == [{"a": 1}]
        and r.total == 1
        and r.last_refresh.startswith("2026-10-15T20")
    )


def test_short_part_fails_capture_naming_the_day(tmp_path):
    snap = snapshot.Snapshot(tmp_path)
    c = _client(
        lambda u, q: {
            "data": [{"a": 1}],
            "lastRefreshTime": "2026-10-15T20:00:00.000Z",
            "total": 2,
        }
    )
    parts = capture_cube.row_queries(
        _checks(), dt.date(2026, 10, 5), dt.date(2026, 10, 5)
    )
    with pytest.raises(capture_cube.CaptureError, match="2026-10-05: 1 of 2 rows"):
        capture_cube.pull_rows(c, snap, parts, BUILT)
    assert not list(snap.cube_parts.iterdir())


def test_stale_answer_is_renewed_once_then_fails(tmp_path):
    seen = []

    def answer(u, q):
        seen.append(q.get("renewQuery"))
        return {"data": [], "lastRefreshTime": "2026-10-15T10:00:00.000Z", "total": 0}

    snap = snapshot.Snapshot(tmp_path)
    parts = capture_cube.row_queries(
        _checks(), dt.date(2026, 10, 5), dt.date(2026, 10, 5)
    )
    with pytest.raises(capture_cube.CaptureError, match="older than"):
        capture_cube.pull_rows(_client(answer), snap, parts, BUILT)
    assert seen == [None, True]


def test_finished_parts_are_kept_and_skipped(tmp_path):
    snap = snapshot.Snapshot(tmp_path)
    (snap.cube_parts / "2026-10-05.json").write_text(
        json.dumps({"rows": [], "total": 0, "last_refresh": "x"})
    )
    c = _client(lambda u, q: pytest.fail("should not ask Cube again"))
    parts = capture_cube.row_queries(
        _checks(), dt.date(2026, 10, 5), dt.date(2026, 10, 5)
    )
    assert (
        capture_cube.pull_rows(c, snap, parts, BUILT)["2026-10-05"]["status"] == "kept"
    )


def test_sql_returns_the_compiled_query_and_params():
    c = _client(lambda u, q: {"sql": {"sql": ["SELECT ?", ["x"]]}})
    assert c.sql({"measures": []}) == ("SELECT ?", ["x"])
