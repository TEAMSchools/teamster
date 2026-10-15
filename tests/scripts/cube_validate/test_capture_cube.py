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
        "https://cube/x", "s" * 32, "me@x", http=FakeHttp(answer), sleep=lambda s: None
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


def test_answer_without_a_refresh_stamp_fails_and_writes_nothing(tmp_path):
    snap = snapshot.Snapshot(tmp_path)
    c = _client(lambda u, q: {"data": [], "total": 0})
    parts = capture_cube.row_queries(
        _checks(), dt.date(2026, 10, 5), dt.date(2026, 10, 5)
    )
    with pytest.raises(capture_cube.CaptureError, match="no lastRefreshTime"):
        capture_cube.pull_rows(c, snap, parts, BUILT)
    assert not list(snap.cube_parts.iterdir())


def _answers_setup(tmp_path, monkeypatch, answer):
    monkeypatch.setattr(
        capture_cube.cells, "cube_query", lambda checks, sheet, cut, click: {"m": 1}
    )
    monkeypatch.setattr(capture_cube.cells, "answer_key", lambda cid, sheet: "k")
    checks = SimpleNamespace(cuts=[SimpleNamespace(id="c")], sheets=["s1"])
    return snapshot.Snapshot(tmp_path), checks, _client(answer)


def test_short_aggregate_answer_is_stored_with_an_error(tmp_path, monkeypatch):
    snap, checks, c = _answers_setup(
        tmp_path,
        monkeypatch,
        lambda u, q: {
            "data": [{"a": 1}],
            "lastRefreshTime": "2026-10-15T20:00:00.000Z",
            "total": 2,
        },
    )
    out = capture_cube.capture_answers(c, snap, checks, {}, BUILT)
    assert out["k"]["error"] == "1 of 2 rows" and out["k"]["query"] == {"m": 1}
    assert "data" not in out["k"]


def test_complete_aggregate_answer_is_stored_with_data_and_sql(tmp_path, monkeypatch):
    def answer(u, q):
        if u.endswith("/sql"):
            return {"sql": {"sql": ["SELECT 1", []]}}
        assert q["total"] is True
        return {
            "data": [{"a": 1}],
            "lastRefreshTime": "2026-10-15T20:00:00.000Z",
            "total": 1,
        }

    snap, checks, c = _answers_setup(tmp_path, monkeypatch, answer)
    out = capture_cube.capture_answers(c, snap, checks, {}, BUILT)
    assert out["k"]["data"] == [{"a": 1}] and out["k"]["sql"] == "SELECT 1"
    assert out["k"]["query"] == {"m": 1}
    assert json.loads(snap.answers.read_text())["k"]["sql"] == "SELECT 1"


def _scope_checks():
    return SimpleNamespace(
        cube=config.CubeRows("v", "attendance_date", ()),
        key=(
            config.Expr("student", "student_number", "lea_student_identifier"),
            config.Expr("school", "school_abbreviation", "locations_abbreviation"),
        ),
        scope_key="school",
    )


def test_scope_query_is_one_grouped_undated_count():
    assert capture_cube.scope_query(_scope_checks()) == {
        "dimensions": ["v.locations_abbreviation"],
        "filters": [],
        "measures": ["v.count_students"],
        "limit": 50000,
        "total": True,
    }


def test_scope_query_carries_cube_filters_but_no_date_filter():
    f = {"member": "v.region", "operator": "equals", "values": ["Newark"]}
    checks = _scope_checks()
    checks.cube = config.CubeRows("v", "attendance_date", (), (f,))
    q = capture_cube.scope_query(checks)
    assert q["filters"] == [f]


def test_capture_scope_returns_the_values_cube_sends_back():
    sent = []

    def answer(u, q):
        sent.append(q)
        return {
            "data": [
                {"v.locations_abbreviation": "TEAM", "v.count_students": 9},
                {"v.locations_abbreviation": "Rise", "v.count_students": 4},
                {"v.locations_abbreviation": None, "v.count_students": 1},
            ],
            "total": 3,
        }

    assert capture_cube.capture_scope(_client(answer), _scope_checks()) == [
        "Rise",
        "TEAM",
    ]
    assert sent == [capture_cube.scope_query(_scope_checks())]


def test_capture_scope_refuses_a_short_answer():
    c = _client(lambda u, q: {"data": [{"v.locations_abbreviation": "R"}], "total": 2})
    with pytest.raises(capture_cube.CaptureError, match="scope"):
        capture_cube.capture_scope(c, _scope_checks())


def test_no_scope_key_means_no_scope_query():
    checks = SimpleNamespace(**{**vars(_scope_checks()), "scope_key": None})
    assert capture_cube.scope_query(checks) is None
    assert capture_cube.capture_scope(_client(lambda u, q: pytest.fail()), checks) == []
