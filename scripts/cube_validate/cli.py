"""Command line: plan, run, answers, analyze, close.

plan, run, answers and close need the Tableau PAT and CUBE_API_SECRET, which
only the pytest secrets fixture provides; run them inside a throwaway
tests/test_zz_*.py (see the cube-dashboard skill). analyze needs nothing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from . import (
    capture_cube,
    capture_tableau,
    cells,
    config,
    cuts,
    handchecks,
    hyper,
    preflight,
    report,
    rows,
    snapshot,
    workbook,
)

COMMANDS = ("plan", "run", "answers", "analyze", "close")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cube_validate")
    sub = p.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        s = sub.add_parser(name)
        s.add_argument("checks", help="path to checks/<dashboard>.yml")
        s.add_argument("--snapshot", help="snapshot folder (default: newest)")
        s.add_argument(
            "--period",
            help="START:END dates to capture, e.g. 2025-07-01:2026-06-30",
        )
    return p


def _period(checks, arg: str | None, today: dt.date) -> tuple[dt.date, dt.date, str]:
    if not arg:
        return checks.period_start, today, ""
    a, b = arg.split(":")
    return dt.date.fromisoformat(a), dt.date.fromisoformat(b), f"{a[:4]}-{b[2:4]}"


def analyze_snapshot(checks, snap) -> tuple[Path, str]:
    """Phases 3 and 4 on a frozen snapshot. Calls nothing outside the snapshot.

    Args:
        checks: The loaded checks file.
        snap: The snapshot to analyze.

    Returns:
        The report path and the trust line.
    """
    m = snapshot.read_manifest(snap)
    answers = json.loads(snap.answers.read_text()) if snap.answers.exists() else {}
    with hyper.Workspace(
        snap.analysis / "analysis.hyper", {"tab": snap.extract, "cub": snap.cube}
    ) as ws:
        rr = rows.build(ws, checks, m.get("scope") or [])
        cs = cells.judge(
            ws, checks, m, answers, lambda cut, sheet: _export(snap, cut, sheet)
        )
        picked = handchecks.pick(
            cs, handchecks.row_samples(ws, checks), seed=snap.dir.name
        )
    handchecks.write(
        snap.analysis, picked, (m.get("review_copy") or {}).get("name", ""), answers
    )
    results = handchecks.read_results(snap.analysis / "hand_checks.yml")
    forms = (
        workbook.formulas(workbook.twb_text(snap.twbx)) if snap.twbx.exists() else {}
    )
    text = report.render(checks, m, rr, cs, results, forms, answers)
    path = snap.analysis / "report.md"
    path.write_text(text)
    return path, report.trust({**(m.get("invariants") or {}), **rr.invariants}, results)


def _export(snap, cut: str, sheet: str) -> bytes | None:
    p = snap.export_path(cut, sheet)
    return p.read_bytes() if p.exists() and p.stat().st_size else None


def _plan(checks) -> int:
    root = snapshot.SNAPSHOT_ROOT / checks.dashboard / "plan"
    root.mkdir(parents=True, exist_ok=True)
    twbx, _ = capture_tableau.download(checks.workbook_luid, root)
    text = workbook.twb_text(twbx)
    wb = workbook.read_workbook(text)
    extracts = workbook.unpack_extracts(twbx, root)
    values: dict[str, list[str]] = {}
    columns: list[str] = []
    if checks.datasource in extracts:
        path = root / extracts[checks.datasource]["file"]
        with hyper.Workspace(root / "scratch.hyper", {"tab": path}) as ws:
            columns = ws.columns("tab", "Extract", "Extract")
            for f in wb.filters:
                if f.field in columns and f.caption not in values:
                    got = ws.query(
                        # trunk-ignore(bandit/B608): field is a column of the downloaded extract
                        f'select distinct "{f.field}" from "tab"."Extract"."Extract" '
                        "order by 1 limit 50"
                    )
                    values[f.caption] = [str(r[0]) for r in got if r[0] is not None]
    out = root / "plan.yml"
    out.write_text(cuts.plan_yaml(wb, list(checks.dashboards), columns, values))
    print(
        f"Draft written to {out}. Edit sheets, mappings and cuts into the checks file."
    )
    return 0


def _built_at(clock: dict[str, str], tables: list[str]) -> dt.datetime:
    cube_tables = [t for t in tables if ".kipptaf_marts." in t] or tables
    return max(dt.datetime.fromisoformat(clock[t]) for t in cube_tables)


def _run(checks, args) -> int:
    now = dt.datetime.now(dt.UTC)
    start, end, tag = _period(checks, args.period, now.date())
    snap = (
        snapshot.Snapshot(Path(args.snapshot))
        if args.snapshot
        else snapshot.new_snapshot(checks.dashboard, now, tag)
    )
    m = snapshot.read_manifest(snap)
    m["period"] = f"{start}:{end}"

    server, auth = capture_tableau.server_from_env()
    with capture_tableau.signed_in(server, auth):
        live = server.workbooks.get_by_id(checks.workbook_luid)
        if live.updated_at is None:
            raise preflight.PreflightError("Tableau reports no extract refresh time")
        why = preflight.check_window(now, live.updated_at, checks.window)
        if why:
            raise preflight.PreflightError(why)
        cube = capture_cube.client_from_env()
        bq = preflight.BigQuery()
        est = preflight.estimate(
            cube, bq, preflight.planned_queries(checks, start, end)
        )
        # trunk-ignore(bandit/B608): table name comes from the reviewed checks file
        _, dash_tables = bq.dry_run(f"select * from `{checks.dashboard_table}`", [])
        tables = sorted(set(est["tables"]) | dash_tables)
        before = m.get("clock_before") or preflight.clock_map(bq, tables)
        gb = est["bytes"] / 1e9
        m.update(
            cost=f"{gb:.2f} GB planned, cap {checks.cost_cap_gb} GB",
            clock_before=before,
            clock_tables=tables,
        )
        snapshot.write_manifest(snap, m)
        if gb > checks.cost_cap_gb:
            raise preflight.PreflightError(
                f"planned {gb:.2f} GB is over the cap of {checks.cost_cap_gb} GB"
            )

        if not snap.twbx.exists():
            twbx, _ = capture_tableau.download(checks.workbook_luid, snap.dir)
            Path(twbx).rename(snap.twbx)
        session = capture_tableau.Session(
            server, checks.review_project_luid, auth=auth, quiet=checks.quiet_minutes
        )
        m.update(capture_tableau.capture(checks, snap, session, now))
        snapshot.write_manifest(snap, m)

    built = _built_at(before, tables)
    parts = capture_cube.pull_rows(
        cube, snap, capture_cube.row_queries(checks, start, end), built
    )
    n, scope = capture_cube.write_cube_hyper(
        snap, checks, cube.member_types(checks.cube.view)
    )
    capture_cube.capture_answers(cube, snap, checks, m, built)
    after = preflight.clock_map(bq, tables)
    moved = preflight.changed(before, after)
    m.update(
        scope=scope,
        scope_size=len(scope),
        clock_after=after,
        clock_risk=", ".join(moved) or "none",
        cube_refresh=f"{len(parts)} parts, {n} rows",
        invariants={**(m.get("invariants") or {}), "capture completeness": True},
    )
    snapshot.write_manifest(snap, m)
    path, trust = analyze_snapshot(checks, snap)
    print(f"{trust}\nReport: {path}")
    return 0


def _answers(checks, args) -> int:
    snap = snapshot.Snapshot(Path(args.snapshot))
    m = snapshot.read_manifest(snap)
    now = dt.datetime.now(dt.UTC)
    extract_at = dt.datetime.fromisoformat(m["extract_refreshed"])
    why = preflight.check_window(now, extract_at, checks.window)
    if why:
        raise preflight.PreflightError(why)
    bq = preflight.BigQuery()
    after = preflight.clock_map(bq, m["clock_tables"])
    moved = preflight.changed(m["clock_before"], after)
    if moved:
        raise preflight.PreflightError(
            f"tables changed since capture: {', '.join(moved)}; run a new capture"
        )
    capture_cube.capture_answers(
        capture_cube.client_from_env(),
        snap,
        checks,
        m,
        _built_at(m["clock_before"], m["clock_tables"]),
    )
    path, trust = analyze_snapshot(checks, snap)
    print(f"{trust}\nReport: {path}")
    return 0


def _close(checks) -> int:
    server, auth = capture_tableau.server_from_env()
    with capture_tableau.signed_in(server, auth):
        session = capture_tableau.Session(server, checks.review_project_luid)
        left = session.review_copies(checks.workbook)
    if not left:
        print("No review copies left in TEMP-CB.")
        return 0
    for w in left:
        print(f"Delete in Tableau: {w.name}: {w.webpage_url}")
    print(capture_tableau.FIND_BY_NAME)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    checks = config.load_checks(args.checks)
    if args.command == "plan":
        return _plan(checks)
    if args.command == "run":
        return _run(checks, args)
    if args.command == "answers":
        return _answers(checks, args)
    if args.command == "close":
        return _close(checks)
    snap = (
        snapshot.Snapshot(Path(args.snapshot))
        if args.snapshot
        else snapshot.latest_snapshot(checks.dashboard)
    )
    path, trust = analyze_snapshot(checks, snap)
    print(f"{trust}\nReport: {path}")
    return 0
