"""Preflight: window, cost, clock map. Fakes only."""

import datetime as dt
from zoneinfo import ZoneInfo

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest registers cube_validate at runtime
from cube_validate import config, preflight

NY = ZoneInfo("America/New_York")
W = config.Window(dt.time(15, 30), dt.time(6), dt.time(15), "America/New_York")


def _ny(d, h, m=0):
    return dt.datetime(2026, 10, d, h, m, tzinfo=NY)


def test_window_accepts_evening_and_overnight_after_todays_refresh():
    assert preflight.check_window(_ny(15, 22), _ny(15, 15, 2), W) == ""
    assert preflight.check_window(_ny(16, 2), _ny(15, 15, 2), W) == ""


def test_window_refuses_daytime_and_a_stale_extract():
    assert "outside" in preflight.check_window(_ny(15, 10), _ny(15, 6, 1), W)
    assert "before" in preflight.check_window(_ny(15, 22), _ny(15, 6, 1), W)


class FakeCube:
    def sql(self, q):
        return f"SELECT /*{len(q.get('dimensions', []))}*/ 1", ["2026-10-05"]


class FakeBQ:
    def dry_run(self, sql, params):
        return 1_000_000, {"p.marts.fct", "p.marts.dim"}

    def modified(self, t):
        return {"p.marts.fct": "2026-10-15T19:05:00+00:00"}.get(
            t, "2026-10-01T00:00:00+00:00"
        )


def test_estimate_sums_bytes_and_collects_tables():
    got = preflight.estimate(
        FakeCube(), FakeBQ(), [("a", {}), ("b", {"dimensions": ["x"]})]
    )
    assert got["bytes"] == 2_000_000
    assert got["tables"] == ["p.marts.dim", "p.marts.fct"]
    assert set(got["sql"]) == {"a", "b"}


def test_estimate_counts_total_queries_twice():
    got = preflight.estimate(FakeCube(), FakeBQ(), [("a", {"total": True}), ("b", {})])
    assert got["bytes"] == 3_000_000


def test_clock_map_and_changes():
    before = preflight.clock_map(FakeBQ(), ["p.marts.fct", "p.marts.dim"])
    after = {**before, "p.marts.dim": "2026-10-15T23:00:00+00:00"}
    assert preflight.changed(before, after) == ["p.marts.dim"]


def test_planned_queries_include_the_scope_query():
    checks = config.Checks(
        dashboard="d",
        workbook="w",
        workbook_luid="l",
        review_project_luid="p",
        dashboards=(),
        datasource="ds",
        dashboard_table="p.d.t",
        period_start=dt.date(2026, 10, 5),
        window=W,
        cost_cap_gb=50,
        quiet_minutes=(0, 10),
        cube=config.CubeRows("v", "attendance_date", ("locations_abbreviation",)),
        key=(
            config.Expr("day", "calendardate", "attendance_date"),
            config.Expr("school", "school_abbreviation", "locations_abbreviation"),
        ),
        compare=(),
        labels=(),
        student_key="day",
        date_key="day",
        scope_key="school",
        causes=(),
        filters={},
        params={},
        sheets={},
        cuts=(config.Cut("default"),),
        excluded_sheets={},
    )
    got = dict(
        preflight.planned_queries(checks, dt.date(2026, 10, 5), dt.date(2026, 10, 5))
    )
    assert got["scope"]["dimensions"] == ["v.locations_abbreviation"]
    assert got["scope"]["measures"] == ["v.count_students"]


def test_estimate_runs_queries_in_parallel():
    import threading

    gate = threading.Barrier(2, timeout=5)

    class GatedCube(FakeCube):
        def sql(self, q):
            gate.wait()  # breaks unless 2 queries are in flight at once
            return super().sql(q)

    got = preflight.estimate(GatedCube(), FakeBQ(), [("a", {}), ("b", {})])
    assert got["bytes"] == 2_000_000 and list(got["sql"]) == ["a", "b"]
