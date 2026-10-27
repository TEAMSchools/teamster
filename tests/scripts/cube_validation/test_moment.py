from datetime import datetime, timedelta, timezone

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.moment import (
    Build,
    MomentError,
    changed_between,
    fact_builds,
    fingerprint,
    pick_moment,
)

NOW = datetime(2026, 10, 27, 12, 0, 0, tzinfo=timezone.utc)


def build(days_ago: float, job_id: str = "j") -> Build:
    start = NOW - timedelta(days=days_ago)

    return Build(start=start, end=start + timedelta(seconds=12), job_id=job_id)


class FakeWh:
    def __init__(self, rows):
        self._rows = rows
        self.sql: list[str] = []

    def rows(self, sql):
        self.sql.append(sql)
        rows = self._rows

        return rows.pop(0) if rows and isinstance(rows[0], list) else rows


def test_pick_latest_build():
    builds = [build(3, "a"), build(1, "b"), build(2, "c")]

    assert pick_moment(builds, NOW, None).job_id == "b"


def test_requested_moment_picks_build_ending_at_or_before():
    builds = [build(3, "a"), build(2, "b"), build(1, "c")]
    requested = builds[1].end + timedelta(hours=1)

    assert pick_moment(builds, NOW, requested).job_id == "b"
    assert pick_moment(builds, NOW, builds[1].end).job_id == "b"


def test_latest_build_outside_window_is_refused():
    with pytest.raises(MomentError, match="7 days"):
        pick_moment([build(7.5, "old")], NOW, None)


def test_literal_keeps_microseconds_and_refuses_naive():
    ts = datetime(2026, 10, 27, 12, 0, 0, 123456, tzinfo=timezone.utc)
    wh = FakeWh([{"f": 1}])
    fingerprint(wh, "ds.t", ts)
    assert "12:00:00.123456+00:00" in wh.sql[0]

    with pytest.raises(ValueError, match="naive"):
        fingerprint(FakeWh([{"f": 1}]), "ds.t", datetime(2026, 10, 27, 12))


def test_requested_moment_outside_window_is_refused():
    builds = [build(7.5, "old"), build(1, "new")]

    with pytest.raises(MomentError, match="7 days"):
        pick_moment(builds, NOW, builds[0].end + timedelta(minutes=1))


def test_requested_before_any_build_is_refused():
    with pytest.raises(MomentError):
        pick_moment([build(1)], NOW, NOW - timedelta(days=3))


def test_requested_moment_older_than_the_window_names_it():
    # The builds list holds only the window, so no build ends that early.
    with pytest.raises(MomentError, match="in the last 7 days ended at or before"):
        pick_moment([build(1)], NOW, NOW - timedelta(days=20), fact="f")


def test_no_build_is_refused():
    with pytest.raises(
        MomentError, match="no successful build of f in the last 7 days"
    ):
        pick_moment([], NOW, None, fact="f")


def test_fact_builds_maps_rows_and_filters_destination():
    rows = [
        {
            "start_time": NOW,
            "end_time": NOW + timedelta(seconds=5),
            "job_id": "j1",
        }
    ]
    wh = FakeWh(rows)

    out = fact_builds(wh, "kipptaf_marts.fct_x", NOW - timedelta(days=5))

    assert out == [Build(NOW, NOW + timedelta(seconds=5), "j1")]
    sql = wh.sql[0]
    assert "INFORMATION_SCHEMA.JOBS_BY_PROJECT" in sql
    assert "`teamster-332318`.`region-us`" in sql
    assert "kipptaf_marts" in sql and "fct_x" in sql
    assert "error_result IS NULL" in sql


def test_fingerprint_queries_table_as_of():
    wh = FakeWh([{"f": 42}])

    assert fingerprint(wh, "ds.t", NOW) == 42
    assert (
        "AS t FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-27 12:00:00.000000+00:00'"
        in wh.sql[0]
    )
    assert "bit_xor(farm_fingerprint(to_json_string(t)))" in wh.sql[0]


def test_changed_between_lists_differing_tables():
    values = {("ds.a", 1): 1, ("ds.a", 2): 1, ("ds.b", 1): 1, ("ds.b", 2): 9}

    class Wh:
        def rows(self, sql):
            table = "ds.a" if "`a`" in sql else "ds.b"
            t = 1 if "10:00:00" in sql else 2

            return [{"f": values[(table, t)]}]

    t1 = datetime(2026, 10, 27, 10, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 27, 11, tzinfo=timezone.utc)

    assert changed_between(Wh(), ["ds.a", "ds.b"], t1, t2) == ["ds.b"]
