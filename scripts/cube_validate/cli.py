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
    coverage,
    cuts,
    decisions,
    handchecks,
    hyper,
    preflight,
    probes,
    report,
    rows,
    snapshot,
    trusted,
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


def analyze_snapshot(
    checks, snap, checks_path: Path | str | None = None
) -> tuple[Path, str]:
    """Phases 3 and 4 on a frozen snapshot. Calls nothing outside the snapshot.

    Args:
        checks: The loaded checks file.
        snap: The snapshot to analyze.
        checks_path: The checks file on disk. With it, trust carries over from
            the dashboard's last trusted snapshot and this run's own trust is
            recorded; without it, neither happens.

    Returns:
        The report path and the trust line.
    """
    m = snapshot.read_manifest(snap)
    answers = json.loads(snap.answers.read_text()) if snap.answers.exists() else {}
    with hyper.Workspace(
        snap.analysis / "analysis.hyper", {"tab": snap.extract, "cub": snap.cube}
    ) as ws:
        rr = rows.build(ws, checks, m.get("scope"), _manifest_period(m))
        twb = _twb_text(snap)
        formats = workbook.display_formats(twb) if twb else {}
        cs = cells.judge(
            ws,
            checks,
            m,
            answers,
            lambda cut, sheet: _export(snap, cut, sheet),
            formats,
        )
        probed = probes.run(ws, checks, cs)
        cs, decided = decisions.apply(checks, cs, probed)
        samples = handchecks.row_samples(ws, checks)
        code = mapping = ""
        old = None
        known = None
        kinds = trusted.kinds(cs, rr)
        if checks_path is not None:
            code = trusted.code_fingerprint(Path(__file__).parent)
            mapping = trusted.mapping_fingerprint(Path(checks_path))
            old = trusted.read(snap.dir.parent)
            if old and old["snapshot"] == snap.dir.name:
                # a snapshot is judged by its own hand checks, never carried from
                # itself; it picks with what it inherited, so they stay the same
                if trusted.fingerprints_match(old, code, mapping) and old.get(
                    "inherited"
                ):
                    known = set(old["inherited"])
                old = None
            elif trusted.fingerprints_match(old, code, mapping) and old is not None:
                known = set(old["kinds"])
        carried = trusted.carries(old, code, mapping, kinds, checks.dashboard)
        picked = handchecks.pick(
            cs, samples, seed=snap.dir.name, answers=answers, known=known
        )
    handchecks.write(
        snap.analysis,
        picked,
        (m.get("review_copy") or {}).get("name", ""),
        answers,
        [
            u
            for u in handchecks.uncovered(cs, samples, picked)
            if u not in (known or ())
        ],
    )
    # trust reads this run's checks; a kept result for one no longer picked
    # counts only when it disagrees
    ids = {h.id for h in picked}
    results = {
        k: v
        for k, v in handchecks.read_results(snap.analysis / "hand_checks.yml").items()
        if k in ids or v == "disagree"
    }
    cover = coverage.lines(checks, cs, rr, twb) if checks.must_cover else None
    from_snap = old["snapshot"] if carried and old else None
    text = report.render(
        checks,
        m,
        rr,
        cs,
        results,
        twb,
        answers,
        decided,
        coverage=cover,
        carried_from=from_snap,
        probes=probed,
    )
    path = snap.analysis / "report.md"
    path.write_text(text)
    line = report.trust(
        {**(m.get("invariants") or {}), **rr.invariants},
        results,
        report.compared(cs),
        carried_from=from_snap,
    )
    if checks_path is not None and line.startswith("Trusted for this run"):
        trusted.record(
            snap.dir.parent,
            snap.dir.name,
            code,
            mapping,
            kinds,
            checks.dashboard,
            inherited=known,
        )
    return path, line


def _twb_text(snap) -> str:
    """The snapshot's workbook XML: base.twb, else the .twbx's, else empty."""
    base = snap.dir / "base.twb"
    if base.exists():
        return base.read_text(encoding="utf-8", newline="")
    return workbook.twb_text(snap.twbx) if snap.twbx.exists() else ""


def _clock_risk(bq, before: dict[str, str], after: dict[str, str]) -> str:
    """The manifest's clock-risk line: rows changed per moved table.

    It runs after the paid capture, so a table BigQuery cannot compare is named
    rather than stopping the run before the manifest is written.
    """
    from google.api_core import exceptions

    moved = preflight.changed(before, after)
    changed, same = [], []
    for t in moved:
        try:
            n, total = preflight.row_diff(bq, t, before[t], after[t])
        except exceptions.GoogleAPIError as e:
            changed.append(f"{t}: rows not compared ({e})")
            continue
        if n:
            changed.append(
                f"{t}: {report.small(n)} of {report.small(total)} rows changed"
            )
        else:
            same.append(t)
    if changed:
        return "; ".join(changed)
    if same:
        return f"none (rebuilt with the same rows: {', '.join(same)})"
    return "none"


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


def _same_rows_noted(bq, before: dict[str, str], moved: list[str]) -> list[str]:
    """The moved tables whose rows changed; names the ones rebuilt unchanged."""
    changed = preflight.rewritten(bq, before, moved) if moved else []
    same = [t for t in moved if t not in changed]
    if same:
        print(f"Rebuilt with the same rows since capture: {', '.join(same)}")
    return changed


def _resume_checks(
    m: dict,
    period_arg: str | None,
    now: dt.datetime,
    window,
    clock_after: dict,
    rows_changed=lambda moved: moved,
) -> tuple[dt.date, dt.date]:
    """Gate a resumed capture: still in the window, tables unmoved, same period.

    Args:
        m: The snapshot's manifest, which already holds clock_before.
        period_arg: The --period given on this run, if any.
        now: The current time.
        window: The capture window.
        clock_after: The tables' modified times, read just now.
        rows_changed: Of the tables whose time moved, those whose rows changed.

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
    moved = rows_changed(preflight.changed(m["clock_before"], clock_after))
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


def _cube_tables(m: dict, recompute) -> list[str]:
    """The base tables Cube's SQL reads: the only ones that can move its answers.

    The dashboard's tables are frozen in the extract once it refreshes, so a
    change there after capture began cannot affect a resume or `answers`.
    Snapshots written before this was recorded get it from fresh dry runs.
    """
    return list(m.get("cube_tables") or recompute())


def _estimate_tables(checks, m: dict, cube, bq) -> list[str]:
    """Cube's base tables for the snapshot's period, from free dry runs."""
    a, b = m["period"].split(":")
    queries = preflight.planned_queries(
        checks, dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    )
    return sorted(preflight.estimate(cube, bq, queries)["tables"])


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
            gate = _cube_tables(m, lambda: _estimate_tables(checks, m, cube, bq))
            start, end = _resume_checks(
                m,
                args.period,
                now,
                checks.window,
                preflight.clock_map(bq, gate),
                lambda moved: _same_rows_noted(bq, m["clock_before"], moved),
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
            dollars = preflight.usd(est["bytes"])
            if dollars > checks.cost_cap_usd:
                raise preflight.PreflightError(
                    f"planned {gb:.2f} GB (about ${dollars:.2f}) is over the cap of "
                    f"${checks.cost_cap_usd:.2f}"
                )
            before = preflight.clock_map(bq, tables)
            m.update(
                period=f"{start}:{end}",
                extract_at=live.updated_at.isoformat(),
                cost=f"{gb:.2f} GB planned (about ${dollars:.2f}), cap ${checks.cost_cap_usd:.2f}",
                clock_before=before,
                clock_tables=tables,
                cube_tables=sorted(est["tables"]),
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
    scope = capture_cube.capture_scope(cube, checks, built)
    if checks.scope_key and not scope:
        print(
            "WARNING: Cube returned an empty scope for this identity; every "
            "dashboard-only row reads outside scope, never as a Cube finding."
        )
    n = capture_cube.write_cube_hyper(snap, checks, cube.member_types(checks.cube.view))
    capture_cube.capture_answers(cube, snap, checks, m, built)
    _print_failed_answers(snap)
    after = preflight.clock_map(bq, tables)
    m.update(
        scope=scope,
        scope_size=len(scope),
        clock_after=after,
        clock_risk=_clock_risk(bq, before, after),
        cube_refresh=f"{len(parts)} parts, {n} rows",
        invariants={**(m.get("invariants") or {}), "capture completeness": True},
    )
    snapshot.write_manifest(snap, m)
    path, trust = analyze_snapshot(checks, snap, args.checks)
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
    cube = capture_cube.client_from_env()
    gate = _cube_tables(m, lambda: _estimate_tables(checks, m, cube, bq))
    after = preflight.clock_map(bq, gate)
    moved = _same_rows_noted(
        bq, m["clock_before"], preflight.changed(m["clock_before"], after)
    )
    if moved:
        raise preflight.PreflightError(
            f"tables Cube reads changed since capture: {', '.join(moved)}; run a new capture"
        )
    capture_cube.capture_answers(
        cube,
        snap,
        checks,
        m,
        _built_at(m["clock_before"], m["clock_tables"]),
    )
    _print_failed_answers(snap)
    path, trust = analyze_snapshot(checks, snap, args.checks)
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
    path, trust = analyze_snapshot(checks, snap, args.checks)
    print(f"{trust}\nReport: {path}")
    return 0
