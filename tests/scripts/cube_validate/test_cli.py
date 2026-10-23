"""analyze end to end on a synthetic snapshot. No live calls."""

import datetime as dt
import json
import shutil

import pytest
import yaml

pytest.importorskip("tableauhyperapi")

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest registers cube_validate at runtime
from cube_validate import cells, cli, hyper, snapshot  # noqa: E402

CHECKS = {
    "dashboard": "d",
    "workbook": "W",
    "workbook_luid": "l",
    "review_project_luid": "ddc817c2-6bc7-4bca-8be9-e385f95b9ebc",
    "dashboards": ["Overview"],
    "datasource": "ds",
    "dashboard_table": "p.d.t",
    "period_start": "2026-10-05",
    "window": {
        "start": "15:30",
        "end": "06:00",
        "extract_after": "15:00",
        "tz": "America/New_York",
    },
    "cost_cap_usd": 5,
    "cube": {
        "view": "v",
        "date": "attendance_date",
        "members": [
            "lea_student_identifier",
            "attendance_date",
            "locations_abbreviation",
        ],
    },
    "rows": {
        "student_key": "student",
        "date_key": "day",
        "scope_key": "school",
        "key": {
            "student": {
                "tableau": "student_number",
                "cube": 'cast("{p}lea_student_identifier" as bigint)',
            },
            "day": {"tableau": "calendardate", "cube": "attendance_date"},
            "school": {
                "tableau": "school_abbreviation",
                "cube": "locations_abbreviation",
            },
        },
    },
    "sheets": {
        "ADA": {
            "students": "Students",
            "dims": {
                "School": {
                    "tableau": "school_abbreviation",
                    "cube": "locations_abbreviation",
                    "cube_column": "locations_abbreviation",
                }
            },
            "measures": {"ADA": {"cube": "avg_daily_attendance"}},
        }
    },
    "cuts": [{"id": "default"}],
}


def test_analyze_writes_report_and_hand_checks(tmp_path):
    checks_path = tmp_path / "c.yml"
    checks_path.write_text(yaml.safe_dump(CHECKS))
    snap = snapshot.new_snapshot("d", dt.datetime(2026, 10, 15, 16, 0), root=tmp_path)
    d = dt.date(2026, 10, 6)
    hyper.write_table(
        snap.extract,
        "Extract",
        "Extract",
        [
            ("student_number", "bigint"),
            ("calendardate", "date"),
            ("school_abbreviation", "text"),
        ],
        [(1, d, "Rise"), (2, d, "Rise")],
    )
    hyper.write_table(
        snap.cube,
        "cube",
        "rows",
        [
            ("lea_student_identifier", "double"),
            ("attendance_date", "date"),
            ("locations_abbreviation", "text"),
        ],
        [(1.0, d, "Rise"), (2.0, d, "Rise")],
    )
    snap.export_path("default", "ADA").write_bytes(
        b"School,ADA,Students\nRise,94.2%,2\n"
    )
    snap.answers.write_text(
        json.dumps(
            {
                cells.answer_key("default", "ADA"): {
                    "query": {},
                    "sql": "SELECT",
                    "last_refresh": "x",
                    "data": [
                        {
                            "v.locations_abbreviation": "Rise",
                            "v.avg_daily_attendance": "0.942",
                        }
                    ],
                }
            }
        )
    )
    snapshot.write_manifest(
        snap,
        {
            "scope": ["Rise"],
            "invariants": {"capture completeness": True},
            "review_copy": {"name": "ZZ-REVIEW x"},
            "cuts": {"default": {}},
        },
    )
    report, trust = cli.analyze_snapshot(cli.config.load_checks(checks_path), snap)
    text = report.read_text()
    assert "| pass | <10 |" in text and trust.startswith("Pending")
    assert (snap.analysis / "hand_checks.md").exists()


def _write_checks(tmp_path):
    p = tmp_path / "c.yml"
    p.write_text(yaml.safe_dump(CHECKS))
    return str(p)


def test_main_analyze_dispatches_on_a_snapshot(tmp_path, capsys):
    checks_path = _write_checks(tmp_path)
    snap = snapshot.new_snapshot("d", dt.datetime(2026, 10, 15, 16, 0), root=tmp_path)
    d = dt.date(2026, 10, 6)
    hyper.write_table(
        snap.extract,
        "Extract",
        "Extract",
        [
            ("student_number", "bigint"),
            ("calendardate", "date"),
            ("school_abbreviation", "text"),
        ],
        [(1, d, "Rise")],
    )
    hyper.write_table(
        snap.cube,
        "cube",
        "rows",
        [
            ("lea_student_identifier", "double"),
            ("attendance_date", "date"),
            ("locations_abbreviation", "text"),
        ],
        [(1.0, d, "Rise")],
    )
    snapshot.write_manifest(snap, {"scope": ["Rise"], "cuts": {"default": {}}})
    assert cli.main(["analyze", checks_path, "--snapshot", str(snap.dir)]) == 0
    assert "Report:" in capsys.readouterr().out


def test_main_answers_needs_a_snapshot(tmp_path):
    with pytest.raises(SystemExit, match="answers needs --snapshot"):
        cli.main(["answers", _write_checks(tmp_path)])


def _resume_manifest():
    return {
        "extract_at": "2026-10-15T19:30:00+00:00",
        "clock_before": {"t": "2026-10-15T18:00:00"},
        "period": "2026-10-05:2026-10-15",
    }


def _resume(tmp_path, m, period=None, now=None, after=None):
    window = cli.config.load_checks(_write_checks(tmp_path)).window
    return cli._resume_checks(
        m,
        period,
        now or dt.datetime(2026, 10, 15, 20, 0, tzinfo=dt.UTC),
        window,
        after or {"t": "2026-10-15T18:00:00"},
    )


def test_resume_checks_returns_the_captured_period(tmp_path):
    assert _resume(tmp_path, _resume_manifest(), "2026-10-05:2026-10-15") == (
        dt.date(2026, 10, 5),
        dt.date(2026, 10, 15),
    )


def test_resume_checks_refuse_outside_the_window(tmp_path):
    with pytest.raises(cli.preflight.PreflightError, match="outside the capture"):
        _resume(
            tmp_path,
            _resume_manifest(),
            now=dt.datetime(2026, 10, 15, 14, 0, tzinfo=dt.UTC),
        )


def test_resume_checks_refuse_a_changed_table(tmp_path):
    with pytest.raises(cli.preflight.PreflightError, match="tables changed"):
        _resume(tmp_path, _resume_manifest(), after={"t": "2026-10-15T19:00:00"})


def test_resume_checks_refuse_a_different_period(tmp_path):
    with pytest.raises(cli.preflight.PreflightError, match="captured period"):
        _resume(tmp_path, _resume_manifest(), "2025-07-01:2026-06-30")


def test_resume_checks_refuse_a_missing_extract_time(tmp_path):
    m = _resume_manifest()
    del m["extract_at"]
    with pytest.raises(cli.preflight.PreflightError, match="no recorded extract time"):
        _resume(tmp_path, m)


def test_analyze_reads_the_period_from_the_manifest(tmp_path):
    checks_path = _write_checks(tmp_path)
    snap = snapshot.new_snapshot("d", dt.datetime(2026, 10, 15, 16, 0), root=tmp_path)
    d = dt.date(2026, 10, 6)
    hyper.write_table(
        snap.extract,
        "Extract",
        "Extract",
        [
            ("student_number", "bigint"),
            ("calendardate", "date"),
            ("school_abbreviation", "text"),
        ],
        [(1, d, "Rise"), (1, dt.date(2025, 10, 6), "Rise")],
    )
    hyper.write_table(
        snap.cube,
        "cube",
        "rows",
        [
            ("lea_student_identifier", "double"),
            ("attendance_date", "date"),
            ("locations_abbreviation", "text"),
        ],
        [(1.0, d, "Rise")],
    )
    snapshot.write_manifest(
        snap,
        {"scope": ["Rise"], "period": "2026-10-05:2026-10-15", "cuts": {"default": {}}},
    )
    path, _ = cli.analyze_snapshot(cli.config.load_checks(checks_path), snap)
    text = path.read_text()
    assert "| outside_period | outside_period |" in text
    assert "dashboard_only" not in text


def _fake_run(tmp_path, monkeypatch, pull_rows):
    """A resumed _run with every outside call faked; returns the snapshot."""
    import contextlib
    from types import SimpleNamespace

    snap = snapshot.new_snapshot("d", dt.datetime(2026, 10, 15, 16, 0), root=tmp_path)
    snap.twbx.write_bytes(b"x")
    snapshot.write_manifest(
        snap,
        {
            **_resume_manifest(),
            "clock_tables": ["t"],
            "cube_tables": ["t"],
            "invariants": {"capture completeness": True},
        },
    )
    fake_cube = SimpleNamespace(member_types=lambda view: {})
    cc, ct, pf = cli.capture_cube, cli.capture_tableau, cli.preflight
    monkeypatch.setattr(cc, "client_from_env", lambda: fake_cube)
    monkeypatch.setattr(pf, "BigQuery", lambda: None)
    monkeypatch.setattr(pf, "clock_map", lambda bq, t: {"t": "2026-10-15T18:00:00"})
    monkeypatch.setattr(ct, "server_from_env", lambda: (None, None))
    monkeypatch.setattr(ct, "signed_in", lambda s, a: contextlib.nullcontext())
    monkeypatch.setattr(ct, "Session", lambda *a, **k: None)
    # capture re-reads the manifest on disk, as the real one does
    monkeypatch.setattr(
        ct, "capture", lambda c, s, sess, now: snapshot.read_manifest(s)
    )
    monkeypatch.setattr(
        cli, "_resume_checks", lambda *a: (dt.date(2026, 10, 5), dt.date(2026, 10, 15))
    )
    monkeypatch.setattr(cc, "pull_rows", pull_rows)
    monkeypatch.setattr(
        cc, "capture_scope", lambda cube, checks, built: ["Rise", "TEAM"]
    )
    monkeypatch.setattr(cc, "write_cube_hyper", lambda s, c, t: 0)
    monkeypatch.setattr(cc, "capture_answers", lambda *a: {})
    monkeypatch.setattr(cli, "analyze_snapshot", lambda c, s, p=None: (s.dir, "ok"))
    checks = cli.config.load_checks(_write_checks(tmp_path))
    args = SimpleNamespace(
        snapshot=str(snap.dir), period=None, checks=_write_checks(tmp_path)
    )
    return snap, lambda: cli._run(checks, args)


def test_run_records_the_scope_cube_reports(tmp_path, monkeypatch):
    snap, run = _fake_run(tmp_path, monkeypatch, lambda *a: {})
    assert run() == 0
    m = snapshot.read_manifest(snap)
    assert m["scope"] == ["Rise", "TEAM"]
    assert m["invariants"]["capture completeness"] is True


def test_run_warns_when_cube_reports_an_empty_scope(tmp_path, monkeypatch, capsys):
    snap, run = _fake_run(tmp_path, monkeypatch, lambda *a: {})
    monkeypatch.setattr(
        cli.capture_cube, "capture_scope", lambda cube, checks, built: []
    )
    assert run() == 0
    out = capsys.readouterr().out
    assert "empty scope" in out and "outside scope" in out
    assert snapshot.read_manifest(snap)["scope"] == []


def test_failed_resume_leaves_no_stale_completeness_flag(tmp_path, monkeypatch):
    def fail(*a):
        raise cli.capture_cube.CaptureError("2026-10-05: 1 of 2 rows")

    snap, run = _fake_run(tmp_path, monkeypatch, fail)
    with pytest.raises(cli.capture_cube.CaptureError):
        run()
    invariants = snapshot.read_manifest(snap).get("invariants") or {}
    assert "capture completeness" not in invariants


def test_analyze_stops_on_a_mistyped_hand_check_result(tmp_path):
    checks = cli.config.load_checks(_write_checks(tmp_path))
    snap = snapshot.new_snapshot("d", dt.datetime(2026, 10, 15, 16, 0), root=tmp_path)
    d = dt.date(2026, 10, 6)
    hyper.write_table(
        snap.extract,
        "Extract",
        "Extract",
        [
            ("student_number", "bigint"),
            ("calendardate", "date"),
            ("school_abbreviation", "text"),
        ],
        [(1, d, "Rise"), (2, d, "Rise")],
    )
    hyper.write_table(
        snap.cube,
        "cube",
        "rows",
        [
            ("lea_student_identifier", "double"),
            ("attendance_date", "date"),
            ("locations_abbreviation", "text"),
        ],
        [(1.0, d, "Rise")],
    )
    snapshot.write_manifest(snap, {"scope": ["Rise"], "cuts": {"default": {}}})
    cli.analyze_snapshot(checks, snap)
    y = snap.analysis / "hand_checks.yml"
    data = yaml.safe_load(y.read_text())
    assert data, "the planted dashboard-only row needs a hand check"
    data[0]["result"] = "yes"
    y.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match=f"{data[0]['id']}: yes"):
        cli.analyze_snapshot(checks, snap)


def _skeleton_checks(tmp_path):
    p = tmp_path / "skeleton.yml"
    p.write_text(yaml.safe_dump({**CHECKS, "datasource": "", "dashboards": []}))
    return cli.config.load_checks(p, for_plan=True)


def _plan_wb():
    return cli.workbook.Workbook(
        dashboards={"Overview": ["ADA"], "Other": ["Trend"]},
        filters=[],
        params=[],
        actions=[],
    )


def test_draft_plan_with_no_datasource_or_dashboards_still_drafts(tmp_path):
    extracts = {"a (x)": {"file": "a"}, "b (y)": {"file": "b"}}
    d = yaml.safe_load(
        cli.draft_plan(_skeleton_checks(tmp_path), _plan_wb(), extracts, tmp_path)
    )
    assert set(d["sheets"]) == {"ADA", "Trend"}
    assert d["dashboards"] == ["Overview", "Other"]
    assert d["datasources"] == ["a (x)", "b (y)"] and d["extract_columns"] == []


def test_draft_plan_reads_columns_from_the_only_extract(tmp_path):
    hyper.write_table(
        tmp_path / "only.hyper", "Extract", "Extract", [("region", "text")], [("A",)]
    )
    d = yaml.safe_load(
        cli.draft_plan(
            _skeleton_checks(tmp_path),
            _plan_wb(),
            {"only (x)": {"file": "only.hyper"}},
            tmp_path,
        )
    )
    assert d["extract_columns"] == ["region"]


def test_cube_tables_prefers_the_recorded_list():
    assert cli._cube_tables({"cube_tables": ["p.m.fct"]}, lambda: ["never"]) == [
        "p.m.fct"
    ]


def test_cube_tables_recomputes_for_older_snapshots():
    assert cli._cube_tables(
        {"clock_tables": ["p.f.x", "p.m.fct"]}, lambda: ["p.m.fct"]
    ) == ["p.m.fct"]


def test_resume_checks_pass_a_rebuild_whose_rows_did_not_change(tmp_path):
    window = cli.config.load_checks(_write_checks(tmp_path)).window
    seen = []

    def same_rows(moved):
        seen.append(moved)
        return []

    got = cli._resume_checks(
        _resume_manifest(),
        None,
        dt.datetime(2026, 10, 15, 20, 0, tzinfo=dt.UTC),
        window,
        {"t": "2026-10-15T19:00:00"},
        same_rows,
    )
    assert got == (dt.date(2026, 10, 5), dt.date(2026, 10, 15)) and seen == [["t"]]


PASSING = b"School,ADA,Students\nRise,94.2%,2\n"
# Cube answers 94.2% and every row matches, so 50.0% reads as a formula gap
FORMULA_GAP = b"School,ADA,Students\nRise,50.0%,2\n"


def _analyzable(tmp_path, tag, export=PASSING, invariants=None):
    """A snapshot with one cell, passing by default; returns (checks, checks_path, snap)."""
    checks_path = tmp_path / "c.yml"
    checks_path.write_text(yaml.safe_dump(CHECKS))
    snap = snapshot.new_snapshot(
        "d", dt.datetime(2026, 10, 15, 16, 0), tag, root=tmp_path
    )
    d = dt.date(2026, 10, 6)
    hyper.write_table(
        snap.extract,
        "Extract",
        "Extract",
        [
            ("student_number", "bigint"),
            ("calendardate", "date"),
            ("school_abbreviation", "text"),
        ],
        [(1, d, "Rise"), (2, d, "Rise")],
    )
    hyper.write_table(
        snap.cube,
        "cube",
        "rows",
        [
            ("lea_student_identifier", "double"),
            ("attendance_date", "date"),
            ("locations_abbreviation", "text"),
        ],
        [(1.0, d, "Rise"), (2.0, d, "Rise")],
    )
    snap.export_path("default", "ADA").write_bytes(export)
    snap.answers.write_text(
        json.dumps(
            {
                cells.answer_key("default", "ADA"): {
                    "query": {},
                    "sql": "SELECT",
                    "last_refresh": "x",
                    "data": [
                        {
                            "v.locations_abbreviation": "Rise",
                            "v.avg_daily_attendance": "0.942",
                        }
                    ],
                }
            }
        )
    )
    snapshot.write_manifest(
        snap,
        {
            "scope": ["Rise"],
            "invariants": invariants or {"capture completeness": True},
            "cuts": {"default": {}},
        },
    )
    return cli.config.load_checks(checks_path), checks_path, snap


def _agree_all(snap):
    y = snap.analysis / "hand_checks.yml"
    data = yaml.safe_load(y.read_text())
    for e in data:
        e["result"] = "agree"
    y.write_text(yaml.safe_dump(data))


def test_a_trusted_run_is_recorded_and_a_later_one_carries(tmp_path):
    checks, cp, first = _analyzable(tmp_path, "a")
    cli.analyze_snapshot(checks, first, cp)
    _agree_all(first)
    _, line = cli.analyze_snapshot(checks, first, cp)
    assert line.startswith("Trusted for this run")
    assert cli.trusted.read(first.dir.parent)["snapshot"] == first.dir.name
    _, _, second = _analyzable(tmp_path, "b")
    path, line = cli.analyze_snapshot(checks, second, cp)
    assert line == (
        f"Trusted: carried over from {first.dir.name} "
        "(code and mapping unchanged, no new verdicts)."
    )
    assert f"carried over from {first.dir.name}" in path.read_text()
    assert yaml.safe_load((second.analysis / "hand_checks.yml").read_text()) == []
    assert cli.trusted.read(first.dir.parent)["snapshot"] == first.dir.name


def test_without_a_checks_path_nothing_is_recorded(tmp_path):
    checks, _, snap = _analyzable(tmp_path, "a")
    cli.analyze_snapshot(checks, snap)
    _agree_all(snap)
    cli.analyze_snapshot(checks, snap)
    assert cli.trusted.read(snap.dir.parent) is None


def test_a_changed_mapping_needs_its_own_hand_checks(tmp_path):
    checks, cp, first = _analyzable(tmp_path, "a")
    cli.analyze_snapshot(checks, first, cp)
    _agree_all(first)
    cli.analyze_snapshot(checks, first, cp)
    _, _, second = _analyzable(tmp_path, "b")
    cp.write_text(yaml.safe_dump({**CHECKS, "cost_cap_usd": 6}))
    _, line = cli.analyze_snapshot(checks, second, cp)
    assert line.startswith("Pending")


def test_reanalyzing_the_recorded_snapshot_keeps_its_hand_checks(tmp_path):
    checks, cp, snap = _analyzable(tmp_path, "a")
    cli.analyze_snapshot(checks, snap, cp)
    _agree_all(snap)
    cli.analyze_snapshot(checks, snap, cp)
    y = snap.analysis / "hand_checks.yml"
    before = y.read_text()
    assert yaml.safe_load(before)
    _, line = cli.analyze_snapshot(checks, snap, cp)
    assert line.startswith("Trusted for this run")
    assert y.read_text() == before


def _trust_first(tmp_path):
    """A trusted snapshot "a" whose one cell passes."""
    checks, cp, first = _analyzable(tmp_path, "a")
    cli.analyze_snapshot(checks, first, cp)
    _agree_all(first)
    _, line = cli.analyze_snapshot(checks, first, cp)
    assert line.startswith("Trusted for this run")
    return checks, cp, first


def test_a_copied_snapshot_never_carries_from_its_original(tmp_path):
    checks, cp, first = _analyzable(tmp_path, "a")
    m = snapshot.read_manifest(first)
    snapshot.write_manifest(first, {**m, "extract_at": "2026-10-15T19:00:00+00:00"})
    cli.analyze_snapshot(checks, first, cp)
    _agree_all(first)
    _, line = cli.analyze_snapshot(checks, first, cp)
    assert line.startswith("Trusted for this run")
    copy = snapshot.Snapshot(first.dir.parent / f"{first.dir.name}-copy")
    shutil.copytree(first.dir, copy.dir, ignore=shutil.ignore_patterns("analysis"))
    _, line = cli.analyze_snapshot(checks, copy, cp)
    assert line.startswith("Pending")


def test_one_new_verdict_gets_hand_checks_for_only_that_verdict(tmp_path):
    checks, cp, _ = _trust_first(tmp_path)
    _, _, second = _analyzable(tmp_path, "b", export=FORMULA_GAP)
    _, line = cli.analyze_snapshot(checks, second, cp)
    assert line.startswith("Pending: 1 of 1 hand checks still open")
    md = (second.analysis / "hand_checks.md").read_text()
    titles = [ln for ln in md.splitlines() if ln.startswith("## ")]
    assert len(titles) == 1 and cells.FORMULA_GAP in titles[0]


def test_a_broken_invariant_beats_a_carry(tmp_path):
    checks, cp, _ = _trust_first(tmp_path)
    _, _, second = _analyzable(
        tmp_path, "b", invariants={"capture completeness": True, "rows balance": False}
    )
    _, line = cli.analyze_snapshot(checks, second, cp)
    assert line == "Not trusted: invariant broken: rows balance."


def test_a_snapshot_trusted_on_new_kinds_only_reanalyzes_as_trusted(tmp_path):
    checks, cp, _ = _trust_first(tmp_path)
    _, _, second = _analyzable(tmp_path, "b", export=FORMULA_GAP)
    cli.analyze_snapshot(checks, second, cp)
    _agree_all(second)
    _, line = cli.analyze_snapshot(checks, second, cp)
    assert line.startswith("Trusted for this run")
    assert cli.trusted.read(second.dir.parent)["snapshot"] == second.dir.name
    y = second.analysis / "hand_checks.yml"
    before = y.read_text()
    _, line = cli.analyze_snapshot(checks, second, cp)
    assert line.startswith("Trusted for this run")
    assert y.read_text() == before


class _FakeBigQuery:
    """row_hashes per table: (earlier, later) Counters, or an error to raise."""

    def __init__(self, tables):
        self.tables = tables

    def row_hashes(self, table, at):
        got = self.tables[table]
        if isinstance(got, Exception):
            raise got
        earlier, later = got
        return earlier if at.minute == 16 else later


BEFORE = "2026-10-16T22:16:00+00:00"
AFTER = "2026-10-16T22:18:00+00:00"


def test_clock_risk_none_when_no_table_moved():
    assert cli._clock_risk(_FakeBigQuery({}), {"t": BEFORE}, {"t": BEFORE}) == "none"


def test_clock_risk_names_tables_rebuilt_with_the_same_rows():
    import collections

    rows = collections.Counter({1: 1, 2: 1})
    bq = _FakeBigQuery({"t": (rows, rows)})
    got = cli._clock_risk(bq, {"t": BEFORE}, {"t": AFTER})
    assert got == "none (rebuilt with the same rows: t)"


def test_clock_risk_counts_changed_rows_masked():
    import collections

    earlier = collections.Counter({i: 1 for i in range(1200)})
    later = collections.Counter({i: 1 for i in range(1, 1203)})
    bq = _FakeBigQuery({"t": (earlier, later)})
    assert cli._clock_risk(bq, {"t": BEFORE}, {"t": AFTER}) == (
        "t: <10 of 1,202 rows changed"
    )


def test_clock_risk_reports_a_table_bigquery_cannot_compare():
    import collections

    from google.api_core import exceptions

    rows = collections.Counter({i: 1 for i in range(20)})
    bq = _FakeBigQuery(
        {
            "a": (rows, collections.Counter()),
            "b": exceptions.BadRequest("outside the time travel window"),
        }
    )
    got = cli._clock_risk(bq, {"a": BEFORE, "b": BEFORE}, {"a": AFTER, "b": AFTER})
    assert got == (
        "a: 20 of 0 rows changed; "
        "b: rows not compared (400 outside the time travel window)"
    )
