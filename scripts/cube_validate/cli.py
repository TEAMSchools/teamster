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
from zoneinfo import ZoneInfo

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
        rr = rows.build(ws, checks, m.get("scope"), _manifest_period(m))
        cs = cells.judge(
            ws, checks, m, answers, lambda cut, sheet: _export(snap, cut, sheet)
        )
        picked = handchecks.pick(
            cs, handchecks.row_samples(ws, checks), seed=snap.dir.name, answers=answers
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
    return path, report.trust(
        {**(m.get("invariants") or {}), **rr.invariants},
        results,
        report.compared(cs),
    )


def _manifest_period(m: dict) -> tuple[dt.date, dt.date] | None:
    """The period capture asked Cube for, from the manifest's START:END."""
    if not m.get("period"):
        return None
    a, b = m["period"].split(":")
    return dt.date.fromisoformat(a), dt.date.fromisoformat(b)


def _export(snap, cut: str, sheet: str) -> bytes | None:
    p = snap.export_path(cut, sheet)
    return p.read_bytes() if p.exists() and p.stat().st_size else None


def _plan(checks) -> int:
    root = snapshot.SNAPSHOT_ROOT / checks.dashboard / "plan"
    root.mkdir(parents=True, exist_ok=True)
    server, auth = capture_tableau.server_from_env()
    with capture_tableau.signed_in(server, auth):
        twbx, _ = capture_tableau.download(checks.workbook_luid, root, server=server)
    wb = workbook.read_workbook(workbook.twb_text(twbx))
    extracts = workbook.unpack_extracts(twbx, root)
    out = root / "plan.yml"
    out.write_text(draft_plan(checks, wb, extracts, root))
    print(
        f"Draft written to {out}. Edit sheets, mappings and cuts into the checks file."
    )
    return 0


def draft_plan(checks, wb, extracts: dict[str, dict], root: Path) -> str:
    """The plan.yml text for a downloaded workbook, from a skeleton checks file.

    Args:
        checks: The checks file, loaded for plan: it may name no datasource or
            dashboards yet.
        wb: The parsed workbook.
        extracts: Each embedded extract's caption and file, from unpack_extracts.
        root: The folder holding the unpacked extracts.

    Returns:
        The draft YAML. Columns and values come from the named datasource, or
        from the workbook's only extract; with neither, they stay empty.
    """
    dashboards = list(checks.dashboards) or list(wb.dashboards)
    name = checks.datasource or (next(iter(extracts)) if len(extracts) == 1 else "")
    values: dict[str, list[str]] = {}
    columns: list[str] = []
    if name in extracts:
        path = root / extracts[name]["file"]
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
    return cuts.plan_yaml(wb, dashboards, columns, values, list(extracts))


def _built_at(clock: dict[str, str], tables: list[str]) -> dt.datetime:
    cube_tables = [t for t in tables if ".kipptaf_marts." in t] or tables
    return max(dt.datetime.fromisoformat(clock[t]) for t in cube_tables)


def _resume_checks(
    m: dict, period_arg: str | None, now: dt.datetime, window, clock_after: dict
) -> tuple[dt.date, dt.date]:
    """Gate a resumed capture: still in the window, tables unmoved, same period.

    Args:
        m: The snapshot's manifest, which already holds clock_before.
        period_arg: The --period given on this run, if any.
        now: The current time.
        window: The capture window.
        clock_after: The tables' modified times, read just now.

    Returns:
        The period start and end the snapshot captured.

    Raises:
        PreflightError: Outside the window, a table changed, or the period differs.
    """
    if not m.get("extract_at"):
        raise preflight.PreflightError(
            "this snapshot has no recorded extract time; run a new capture"
        )
    why = preflight.check_window(
        now, dt.datetime.fromisoformat(m["extract_at"]), window
    )
    if why:
        raise preflight.PreflightError(why)
    moved = preflight.changed(m["clock_before"], clock_after)
    if moved:
        raise preflight.PreflightError(
            f"tables changed since capture began: {', '.join(moved)}; run a new capture"
        )
    if period_arg and period_arg != m["period"]:
        raise preflight.PreflightError(
            f"this snapshot captured period {m['period']}; "
            f"start a new run for {period_arg}"
        )
    period = _manifest_period(m)
    if period is None:
        raise preflight.PreflightError("this snapshot has no recorded period")
    return period


def _drop_completeness(m: dict) -> None:
    """Forget an earlier attempt's capture completeness; only pull_rows sets it."""
    (m.get("invariants") or {}).pop("capture completeness", None)


def _run(checks, args) -> int:
    now = dt.datetime.now(dt.UTC)
    snap = snapshot.Snapshot(Path(args.snapshot)) if args.snapshot else None
    m = snapshot.read_manifest(snap) if snap else {}
    # a flag left by an earlier attempt must not survive a failed resume
    _drop_completeness(m)
    resuming = bool(m.get("clock_before"))

    cube = capture_cube.client_from_env()
    bq = preflight.BigQuery()
    server, auth = capture_tableau.server_from_env()
    with capture_tableau.signed_in(server, auth):
        if resuming:
            tables = m["clock_tables"]
            before = m["clock_before"]
            start, end = _resume_checks(
                m,
                args.period,
                now,
                checks.window,
                preflight.clock_map(bq, tables),
            )
        else:
            today = now.astimezone(ZoneInfo(checks.window.tz)).date()
            start, end, tag = _period(checks, args.period, today)
            live = server.workbooks.get_by_id(checks.workbook_luid)
            if live.updated_at is None:
                raise preflight.PreflightError(
                    "Tableau reports no extract refresh time"
                )
            why = preflight.check_window(now, live.updated_at, checks.window)
            if why:
                raise preflight.PreflightError(why)
            est = preflight.estimate(
                cube, bq, preflight.planned_queries(checks, start, end)
            )
            # trunk-ignore(bandit/B608): table name comes from the reviewed checks file
            _, dash_tables = bq.dry_run(f"select * from `{checks.dashboard_table}`", [])
            tables = sorted(set(est["tables"]) | dash_tables)
            gb = est["bytes"] / 1e9
            if gb > checks.cost_cap_gb:
                raise preflight.PreflightError(
                    f"planned {gb:.2f} GB is over the cap of {checks.cost_cap_gb} GB"
                )
            before = preflight.clock_map(bq, tables)
            m.update(
                period=f"{start}:{end}",
                extract_at=live.updated_at.isoformat(),
                cost=f"{gb:.2f} GB planned, cap {checks.cost_cap_gb} GB",
                clock_before=before,
                clock_tables=tables,
            )
            if snap is None:
                snap = snapshot.new_snapshot(checks.dashboard, now, tag)
            snapshot.write_manifest(snap, m)

        if snap is None:  # a resume always names its snapshot
            raise preflight.PreflightError("run needs a snapshot to resume")
        if not snap.twbx.exists():
            twbx, _ = capture_tableau.download(
                checks.workbook_luid, snap.dir, server=server
            )
            Path(twbx).rename(snap.twbx)
        session = capture_tableau.Session(
            server, checks.review_project_luid, auth=auth, quiet=checks.quiet_minutes
        )
        # capture re-reads the manifest on disk, which may still hold the flag
        m.update(capture_tableau.capture(checks, snap, session, now))
        _drop_completeness(m)
        snapshot.write_manifest(snap, m)

    built = _built_at(before, tables)
    parts = capture_cube.pull_rows(
        cube, snap, capture_cube.row_queries(checks, start, end), built
    )
    scope = capture_cube.capture_scope(cube, checks)
    if checks.scope_key and not scope:
        print(
            "WARNING: Cube returned an empty scope for this identity; every "
            "dashboard-only row reads outside scope, never as a Cube finding."
        )
    n = capture_cube.write_cube_hyper(snap, checks, cube.member_types(checks.cube.view))
    capture_cube.capture_answers(cube, snap, checks, m, built)
    _print_failed_answers(snap)
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


def _print_failed_answers(snap) -> None:
    """Name each answer Cube could not give; its cells show as unproven."""
    if not snap.answers.exists():
        return
    for key, entry in json.loads(snap.answers.read_text()).items():
        if isinstance(entry, dict) and entry.get("error"):
            print(f"Cube answer failed: {key}: {entry['error']}")


def _answers(checks, args) -> int:
    if not args.snapshot:
        raise SystemExit("answers needs --snapshot <dir>")
    snap = snapshot.Snapshot(Path(args.snapshot))
    m = snapshot.read_manifest(snap)
    now = dt.datetime.now(dt.UTC)
    if not m.get("extract_at"):
        raise preflight.PreflightError(
            "this snapshot has no recorded extract time; run a new capture"
        )
    extract_at = dt.datetime.fromisoformat(m["extract_at"])
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
    _print_failed_answers(snap)
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
    checks = config.load_checks(args.checks, for_plan=args.command == "plan")
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
