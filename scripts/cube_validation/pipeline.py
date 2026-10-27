"""What each command does, wired from the other modules.

`cli.py` parses arguments and builds the clients; the functions here take those
clients as arguments so tests can pass fakes. The dashboard side is read as of
a fact build's start and Cube as of its end. Every BigQuery query runs inside
`Warehouse.budget`, and only aggregates come back: row-level comparisons run
inside BigQuery through `compare.reconcile_sql`.
"""

from __future__ import annotations

import dataclasses
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import tableauserverclient as TSC

from . import checks, compare, decisions
from . import discover as finder
from . import report, tableau
from .bq import Warehouse
from .checks import CheckResult, Finding
from .compare import Group
from .config import ColumnPair, Comparison, Decision, ViewConfig, write_proof
from .cube_client import (
    Compiled,
    Cube,
    bind,
    drop_limit,
    network_schools,
    refuse_unless_safe,
)
from .decisions import Applied
from .moment import WINDOW, Build, changed_between, fact_builds, pick_moment
from .report import MeasureResult, RunResult
from .timetravel import PROJECT, as_of

API_DECIMALS = checks.DECIMALS
CHECK_API_CUTS = 3
# A proof's probe is time-travelled to the refresh; keep a margin inside 7 days.
PROOF_WINDOW = WINDOW - timedelta(hours=1)


class Refusal(RuntimeError):
    """A command stopped on purpose; the message says why."""


Clock = Callable[[], datetime]


# --- filters and queries -----------------------------------------------------


def _cuts(comparison: Comparison) -> list[dict[str, Any]]:
    return comparison.cuts or [{}]


def cut_label(cut: dict[str, Any]) -> str:
    """Name a cut the same way everywhere: `{}` is the default filter state."""
    return json.dumps(cut, sort_keys=True, default=str)


def effective_filters(comparison: Comparison, cut: dict[str, Any]) -> dict[str, Any]:
    """Return the defaults with the cut's own captions replacing them."""
    merged = {**comparison.defaults, **cut}
    unknown = [c for c in merged if c not in comparison.filters]
    if unknown:
        raise Refusal(
            f"comparison {comparison.id!r}: no `filters` entry for "
            f"{', '.join(map(repr, unknown))}"
        )
    return merged


def _values(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _cube_text(value: Any) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


def _member(view: str, name: str) -> str:
    return name if "." in name else f"{view}.{name}"


def _cut_cube_filters(
    view: str, comparison: Comparison, cut: dict[str, Any]
) -> list[dict]:
    return [
        {
            "member": _member(view, comparison.filters[caption].cube),
            "operator": "equals",
            "values": [_cube_text(v) for v in _values(value)],
        }
        for caption, value in effective_filters(comparison, cut).items()
    ]


def _scope_cube_filters(view: str, comparison: Comparison) -> list[dict]:
    return [
        {**f, "member": _member(view, f["member"])}
        for f in compare.scope_filters(comparison)
    ]


def _lit(value: Any) -> str:
    """A BigQuery literal, escaped the way Cube's parameters are bound."""
    return bind(Compiled("?", [value], []))


def _column_predicate(column: str, value: Any) -> str:
    direct = [v for v in _values(value) if isinstance(v, (bool, int, float))]
    text = [str(v) for v in _values(value) if not isinstance(v, (bool, int, float))]
    parts = []
    if text:
        parts.append(f"CAST({column} AS STRING) IN ({', '.join(map(_lit, text))})")
    if direct:
        parts.append(f"{column} IN ({', '.join(map(_lit, direct))})")
    return parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")"


def dashboard_predicate(comparison: Comparison, cut: dict[str, Any]) -> str:
    """Return the WHERE predicate a cut puts on the dashboard rows."""
    parts = [
        _column_predicate(comparison.filters[caption].dashboard, value)
        for caption, value in effective_filters(comparison, cut).items()
    ]
    return " AND ".join(parts) or "TRUE"


def _any_cut_predicate(comparison: Comparison) -> str:
    """OR of every cut, so a row-level reconcile counts each row once."""
    preds = [dashboard_predicate(comparison, cut) for cut in _cuts(comparison)]
    if "TRUE" in preds:
        return "TRUE"
    return preds[0] if len(preds) == 1 else " OR ".join(f"({p})" for p in preds)


def _any_cut_cube_filters(view: str, comparison: Comparison) -> list[dict]:
    per_cut = [_cut_cube_filters(view, comparison, cut) for cut in _cuts(comparison)]
    if any(not f for f in per_cut):
        return []
    if len(per_cut) == 1:
        return per_cut[0]
    return [{"or": [{"and": f} for f in per_cut]}]


def cell_query(
    view: str, comparison: Comparison, cut: dict[str, Any], with_dims: bool = True
) -> dict:
    """Return the Cube query for a comparison's cells under one cut."""
    dims = comparison.dims if with_dims else []
    return {
        "measures": [_member(view, comparison.measure)],
        "dimensions": [_member(view, d.cube) for d in dims],
        "filters": _cut_cube_filters(view, comparison, cut)
        + _scope_cube_filters(view, comparison),
    }


def _row_pairs(comparison: Comparison) -> list[ColumnPair]:
    rows = comparison.rows
    if rows is None:
        return list(comparison.dims)
    return [*rows.grain, *rows.values, *comparison.dims]


def _unique(names: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(names))


def row_query(view: str, comparison: Comparison) -> dict:
    """Return the ungrouped Cube query for a comparison's rows over every cut."""
    return {
        "dimensions": [
            _member(view, c) for c in _unique(p.cube for p in _row_pairs(comparison))
        ],
        "filters": _any_cut_cube_filters(view, comparison)
        + _scope_cube_filters(view, comparison),
        "ungrouped": True,
    }


def _dashboard_ref(comparison: Comparison) -> str:
    if not comparison.dashboard_view or comparison.dashboard_view.count(".") != 1:
        raise Refusal(
            f"comparison {comparison.id!r}: `dashboard_view` must be dataset.view"
        )
    ds, name = comparison.dashboard_view.split(".")
    return f"`{PROJECT}`.`{ds}`.`{name}`"


def _date_cubes(cfg: ViewConfig) -> set[str]:
    return {cfg.time_dimension} if cfg.time_dimension else set()


def _select(name: str, source: str, is_date: bool) -> str:
    return f"DATE({source}) AS {name}" if is_date else f"{source} AS {name}"


def dashboard_rows_sql(cfg: ViewConfig, comparison: Comparison) -> str:
    """Return the dashboard's rows for the row-level reconcile, every cut."""
    dates = _date_cubes(cfg)
    seen: dict[str, bool] = {}
    for p in _row_pairs(comparison):
        seen.setdefault(p.dashboard, p.cube in dates)
    cols = [
        f"DATE({name}) AS {name}" if is_date else name for name, is_date in seen.items()
    ]
    return (
        f"SELECT {', '.join(cols)} FROM {_dashboard_ref(comparison)} "
        f"WHERE {_any_cut_predicate(comparison)}"
    )


def probe_sql(cfg: ViewConfig, comparison: Comparison, cut: dict[str, Any]) -> str:
    """Return the probe over the dashboard rows under one cut, before time travel.

    `probe` is an aggregate over the rows; `probe_sql` is a template whose
    `{rows}`, `{where}` and `{dims}` are filled here.
    """
    rows = f"SELECT * FROM {_dashboard_ref(comparison)}"
    where = dashboard_predicate(comparison, cut)
    names = [d.dashboard for d in comparison.dims]
    if comparison.probe_sql:
        return comparison.probe_sql.format(
            rows=rows, where=where, dims=", ".join(names)
        )
    if not comparison.probe:
        raise Refusal(f"comparison {comparison.id!r} has no probe or probe_sql")
    dates = _date_cubes(cfg)
    select = [
        f"DATE({d.dashboard}) AS {d.dashboard}" if d.cube in dates else d.dashboard
        for d in comparison.dims
    ]
    group = (
        " GROUP BY " + ", ".join(str(i + 1) for i in range(len(select)))
        if select
        else ""
    )
    return (
        f"SELECT {', '.join([*select, f'{comparison.probe} AS value'])} "
        f"FROM ({rows}) WHERE {where}{group}"
    )


def wrap_cube(
    sql: str, view: str, columns: list[str], dates: set[str], measure: str | None
) -> str:
    """Rename Cube's `<view>__<member>` columns to member names.

    The measure, when given, comes out as `value`. A time dimension in
    `dates` is cast to DATE, as the dashboard side is.
    """
    select = [_select(c, f"`{view}__{c}`", c in dates) for c in columns]
    if measure:
        select.append(f"`{view}__{measure}` AS value")
    return f"SELECT {', '.join(select)} FROM (\n{sql}\n)"


# --- cells -------------------------------------------------------------------


def _key(value: Any) -> str:
    """Cell key text: dates by day, numbers by value, else the text."""
    if isinstance(value, str) and re.match(r"\d{4}-\d{2}-\d{2}", value):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            pass
    if isinstance(value, datetime):
        stamp = value.replace(tzinfo=None)
        return stamp.date().isoformat() if stamp.time() == time() else stamp.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return ""
    text = str(value).strip()
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text
    return format(number.normalize(), "f") if number.is_finite() else text


def _number(value: Any) -> float | None:
    return None if value is None else float(value)


@dataclasses.dataclass(frozen=True)
class Cell:
    comparison: str
    cut: str
    key: str
    dashboard: float | None
    cube: float | None
    verdict: str


def _cells(
    comparison: Comparison,
    cut: dict[str, Any],
    dash_rows: list[dict],
    cube_rows: list[dict],
    decimals: int,
) -> list[Cell]:
    dash = {
        tuple(_key(r[d.dashboard]) for d in comparison.dims): _number(r["value"])
        for r in dash_rows
    }
    cube = {
        tuple(_key(r[d.cube]) for d in comparison.dims): _number(r["value"])
        for r in cube_rows
    }
    cells = []
    for key in sorted(dash.keys() | cube.keys()):
        label = ", ".join(
            f"{d.cube}={v}" for d, v in zip(comparison.dims, key, strict=True)
        )
        cells.append(
            Cell(
                comparison.id,
                cut_label(cut),
                label or "(total)",
                dash.get(key),
                cube.get(key),
                compare.cell_verdict(dash.get(key), cube.get(key), decimals),
            )
        )
    return cells


# --- run ---------------------------------------------------------------------


def _require(comparison: Comparison, *keys: str) -> None:
    missing = [k for k in keys if getattr(comparison, k) in (None, "")]
    if missing:
        raise Refusal(f"comparison {comparison.id!r} has no {', '.join(missing)}")


def comparison_fingerprints(
    cfg: ViewConfig, comparison: Comparison, cube: Cube
) -> dict[str, str]:
    """Fingerprint a comparison's definitions on both sides.

    The Cube side is the bound SQL of the default cut's cells; the dashboard
    side is the default cut's probe plus the row-level SQL. Both are taken
    before time travel, so the moment never changes them.
    """
    compiled = cube.compiled(cell_query(cfg.view, comparison, {}))
    dashboard = probe_sql(cfg, comparison, {})
    if comparison.rows is not None:
        dashboard += "\n" + dashboard_rows_sql(cfg, comparison)
    return {
        "cube": decisions.sql_fingerprint(bind(compiled)),
        "dashboard": decisions.sql_fingerprint(dashboard),
    }


@dataclasses.dataclass
class _Sides:
    """What a run collects across comparisons."""

    cube_tables: set[str] = dataclasses.field(default_factory=set)
    live: set[str] = dataclasses.field(default_factory=set)
    cells: list[Cell] = dataclasses.field(default_factory=list)
    groups: list[Group] = dataclasses.field(default_factory=list)
    clauses: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    sql: dict[str, tuple[str, str]] = dataclasses.field(default_factory=dict)


def _cube_sql(
    cfg: ViewConfig,
    cube: Cube,
    query: dict,
    schools: set[str],
    *,
    rows: bool = False,
) -> str:
    compiled = cube.compiled(query)
    refuse_unless_safe(compiled, view_fact=cfg.fact, network_schools=schools)
    bound = bind(compiled)
    return drop_limit(bound) if rows else bound


def _compare_one(
    cfg: ViewConfig,
    comparison: Comparison,
    *,
    wh: Warehouse,
    cube: Cube,
    build: Build,
    schools: set[str],
    sides: _Sides,
) -> None:
    dates = _date_cubes(cfg)
    dims = [d.cube for d in comparison.dims]

    for cut in _cuts(comparison):
        cube_sql = _cube_sql(cfg, cube, cell_query(cfg.view, comparison, cut), schools)
        cube_at = as_of(cube_sql, build.end, wh)
        dash_at = as_of(probe_sql(cfg, comparison, cut), build.start, wh)
        sides.cube_tables |= cube_at.tables
        sides.live |= cube_at.live | dash_at.live
        cube_rows = wh.rows(
            wrap_cube(cube_at.sql, cfg.view, dims, dates, comparison.measure)
        )
        dash_rows = wh.rows(dash_at.sql)
        sides.cells += _cells(
            comparison, cut, dash_rows, cube_rows, comparison.decimals or 0
        )

    if comparison.rows is None:
        return

    cube_sql = _cube_sql(cfg, cube, row_query(cfg.view, comparison), schools, rows=True)
    cube_at = as_of(cube_sql, build.end, wh)
    dash_at = as_of(dashboard_rows_sql(cfg, comparison), build.start, wh)
    sides.cube_tables |= cube_at.tables
    sides.live |= cube_at.live | dash_at.live
    columns = _unique(p.cube for p in _row_pairs(comparison))
    result = wh.rows(
        compare.reconcile_sql(
            wrap_cube(cube_at.sql, cfg.view, columns, dates, None),
            dash_at.sql,
            comparison.rows,
            comparison.dims,
        )
    )
    sides.groups += compare.groups_from(comparison.id, result)
    sides.sql[comparison.id] = (dash_at.sql, cube_at.sql)


def _clauses(comparison: Comparison, groups: list[Group], sides: _Sides) -> list[str]:
    if comparison.id not in sides.sql:
        return []
    by_cube = {d.cube: d.dashboard for d in comparison.dims}
    columns = _unique(
        name
        for g in groups
        if g.comparison_id == comparison.id and g.column
        for name in (g.column, by_cube.get(g.column, g.column))
    )
    if not columns:
        return []
    dash_sql, cube_sql = sides.sql[comparison.id]
    return _unique(
        compare.clauses_for(columns, dash_sql) + compare.clauses_for(columns, cube_sql)
    )


def _identity_cuts(cfg: ViewConfig, comparisons: list[Comparison]) -> list[dict]:
    """Each comparison cut, keyed by Cube member, for the identities."""
    cuts: dict[str, dict] = {}
    for comparison in comparisons:
        for cut in _cuts(comparison):
            mapped = {
                comparison.filters[caption].cube: value
                for caption, value in effective_filters(comparison, cut).items()
            }
            cuts.setdefault(cut_label(mapped), mapped)
    return list(cuts.values()) or [{}]


def _load_value(cube: Cube, query: dict, member: str) -> float | None:
    rows = cube.load(query)
    if not rows or rows[0].get(member) is None:
        return None
    return float(rows[0][member])


def _anchors_and_identities(
    cfg: ViewConfig, cube: Cube, comparisons: list[Comparison]
) -> tuple[list[Finding], dict[str, list[CheckResult]]]:
    """Run anchors and identities through `Cube.load` on current data."""
    findings: list[Finding] = []
    results: dict[str, list[CheckResult]] = {}

    for anchor in cfg.anchors:
        # load_view_config requires time_dimension whenever anchors are set.
        value = _load_value(
            cube,
            checks.anchor_query(anchor, cfg.view, cfg.time_dimension or ""),
            _member(cfg.view, anchor.measure),
        )
        findings.append(
            checks.anchor_finding(anchor, float("nan") if value is None else value)
        )
        results.setdefault(anchor.measure, []).append(CheckResult("anchor", False))

    for identity in cfg.identities:
        for cut in _identity_cuts(cfg, comparisons):
            left_q, right_q = checks.identity_queries(identity, cut, cfg.view)
            left = _load_value(cube, left_q, _member(cfg.view, identity.left))
            right_rows = cube.load(right_q)
            right_row = right_rows[0] if right_rows else {}
            right = {
                m.split(".", 1)[1]: _number(right_row.get(m))
                for m in right_q["measures"]
            }
            # trunk-ignore(pyright/reportArgumentType): identity_finding fails a None side
            finding = checks.identity_finding(identity, left, right)
            finding = dataclasses.replace(
                finding, detail=f"{finding.detail} (cut {cut_label(cut)})"
            )
            findings.append(finding)
            results.setdefault(identity.left, []).append(
                CheckResult("identity", finding.passed)
            )
    return findings, results


def _measures(
    comparisons: list[Comparison],
    cells: list[Cell],
    other: dict[str, list[CheckResult]],
) -> list[MeasureResult]:
    results: dict[str, list[CheckResult]] = {}
    counts: dict[str, Counter] = {}
    for comparison in comparisons:
        mine = [c for c in cells if c.comparison == comparison.id]
        passed = bool(mine) and all(c.verdict == "pass" for c in mine)
        results.setdefault(comparison.measure, []).append(
            CheckResult("dashboard", passed)
        )
        counts.setdefault(comparison.measure, Counter()).update(c.verdict for c in mine)
    for measure, found in other.items():
        results.setdefault(measure, []).extend(found)
    return [
        MeasureResult(
            measure,
            checks.strongest_check(measure, found),
            checks.verdict(found),
            dict(counts.get(measure, {})),
        )
        for measure, found in results.items()
    ]


def _extra_sections(cells: list[Cell], findings: list[Finding]) -> str:
    out = ["## Cells", ""]
    out += [
        f"- {c.comparison} {c.cut} {c.key}: dashboard {c.dashboard}, "
        f"Cube {c.cube} ({c.verdict})"
        for c in cells
    ] or ["None."]
    out += ["", "## Anchors and identities", ""]
    out += [
        f"- {f.kind} `{f.measure}`: {f.detail} "
        f"({'passes' if f.passed else 'to judge' if f.kind == 'anchor' else 'fails'})"
        for f in findings
    ] or ["None."]
    return "\n".join(out) + "\n"


def run(
    cfg: ViewConfig,
    *,
    wh: Warehouse,
    cube: Cube,
    now: datetime,
    requested: datetime | None,
    max_usd: float,
    cache_root: Path,
) -> RunResult:
    """Validate one view at one fact build and print the result.

    Raises:
        Refusal: A confirmed comparison has no proof or lacks a key it needs.
        CostCapError: The priced queries passed `max_usd`.
        MomentError: No usable build in the 7-day window.
        CubeRefusal: Cube's SQL would not match a raw rebuild.
    """
    comparisons = [c for c in cfg.comparisons if c.confirmed]
    for skipped in (c for c in cfg.comparisons if not c.confirmed):
        print(f"Skipping comparison {skipped.id!r}: not confirmed.")
    if not comparisons:
        raise Refusal(f"{cfg.view}: no confirmed comparison to run")
    unproven = [c.id for c in comparisons if c.proof is None]
    if unproven:
        raise Refusal(
            f"comparison {', '.join(map(repr, unproven))} has no proof; "
            "run `prove` first"
        )
    for comparison in comparisons:
        _require(comparison, "dashboard_view", "decimals")
        if comparison.proof:
            print(f"Proof for {comparison.id}: proven {comparison.proof.proven_at}.")

    with wh.budget(max_usd):
        builds = fact_builds(wh, cfg.fact, since=now - WINDOW)
        build = pick_moment(builds, now, requested, cfg.fact)
        schools = network_schools(wh)
        sides = _Sides()
        fingerprints = {
            c.id: comparison_fingerprints(cfg, c, cube) for c in comparisons
        }
        for comparison in comparisons:
            _compare_one(
                cfg,
                comparison,
                wh=wh,
                cube=cube,
                build=build,
                schools=schools,
                sides=sides,
            )
        dims = sorted(sides.cube_tables - {cfg.fact})
        changed = changed_between(wh, dims, build.start, build.end)
        cost = wh.spent

    findings, other = _anchors_and_identities(cfg, cube, comparisons)
    try:
        applied = decisions.apply(cfg.decisions, sides.groups, fingerprints)
    except ValueError as exc:
        raise Refusal(str(exc)) from exc

    clauses = {c.id: _clauses(c, applied.open, sides) for c in comparisons}
    result = RunResult(
        view=cfg.view,
        moment=build,
        measures=_measures(comparisons, sides.cells, other),
        applied=applied,
        findings=findings,
        live_sources=sorted(sides.live),
        changed_dims=changed,
        scopes=[
            f"{c.id}: {f['member']} in {', '.join(map(str, f['values']))}"
            for c in comparisons
            for f in _scope_cube_filters(cfg.view, c)
        ],
        cost_usd=cost,
        proofs={c.id: c.proof.proven_at for c in comparisons if c.proof},
        clauses={k: v for k, v in clauses.items() if v},
    )
    text = report.render_local(result) + "\n" + _extra_sections(sides.cells, findings)
    print(text)
    saved = report.save_local(result, text, root=cache_root)
    saved.with_name("run.json").write_text(
        json.dumps(dataclasses.asdict(result), default=_json_default, indent=1)
    )
    print(f"Saved {saved}")
    return result


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _run_from_json(data: dict) -> RunResult:
    moment = data["moment"]
    applied = data["applied"]
    return RunResult(
        view=data["view"],
        moment=Build(
            datetime.fromisoformat(moment["start"]),
            datetime.fromisoformat(moment["end"]),
            moment["job_id"],
        ),
        measures=[MeasureResult(**m) for m in data["measures"]],
        applied=Applied(
            open=[Group(**g) for g in applied["open"]],
            quiet=[(Decision(**d), Group(**g)) for d, g in applied["quiet"]],
            reconfirm=[Decision(**d) for d in applied["reconfirm"]],
            no_longer_needed=[Decision(**d) for d in applied["no_longer_needed"]],
        ),
        findings=[Finding(**f) for f in data["findings"]],
        live_sources=data["live_sources"],
        changed_dims=data["changed_dims"],
        scopes=data["scopes"],
        cost_usd=data["cost_usd"],
        proofs=data["proofs"],
        browser_cuts=data["browser_cuts"],
        clauses=data["clauses"],
    )


# --- review ------------------------------------------------------------------


def review(configs: list[ViewConfig], domain: str, cache_root: Path) -> str:
    """Return the review-issue body from each view's latest saved run.

    Reads only the local cache; nothing is posted.

    Raises:
        Refusal: A view has no saved run.
    """
    runs = []
    for cfg in configs:
        saved = sorted((cache_root / cfg.view).glob("*/run.json"))
        if not saved:
            raise Refusal(f"{cfg.view}: no saved run; `run` it first")
        runs.append(_run_from_json(json.loads(saved[-1].read_text())))
    return report.render_review_issue(domain, runs)


# --- check-api ---------------------------------------------------------------


def _api_checks(cfg: ViewConfig) -> list[tuple[Comparison, dict, bool]]:
    """The default cut by dims, then the other cuts, then the default total."""
    picks: list[tuple[Comparison, dict, bool]] = []
    for comparison in cfg.comparisons:
        picks.append((comparison, {}, True))
        picks += [(comparison, cut, True) for cut in comparison.cuts if cut]
        picks.append((comparison, {}, False))
    unique: dict[str, tuple[Comparison, dict, bool]] = {}
    for comparison, cut, with_dims in picks:
        if with_dims and not comparison.dims:
            continue
        query = cell_query(cfg.view, comparison, cut, with_dims)
        unique.setdefault(
            json.dumps(query, sort_keys=True), (comparison, cut, with_dims)
        )
    return list(unique.values())[:CHECK_API_CUTS]


def _same(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return round(a, API_DECIMALS) == round(b, API_DECIMALS)


def check_api(
    cfg: ViewConfig, *, wh: Warehouse, cube: Cube, clock: Clock, max_usd: float
) -> None:
    """Check that `Cube.load` and the bound compiled SQL agree, run now.

    Raises:
        Refusal: They disagree on a cell, or a table they read rebuilt while
            the check ran.
    """
    picks = _api_checks(cfg)
    disagreements: list[str] = []
    tables: set[str] = set()
    with wh.budget(max_usd):
        schools = network_schools(wh)
        first = clock()
        for comparison, cut, with_dims in picks:
            query = cell_query(cfg.view, comparison, cut, with_dims)
            bound = _cube_sql(cfg, cube, query, schools)
            tables |= as_of(bound, first, wh).tables
            dims = [d.cube for d in comparison.dims] if with_dims else []
            api = {
                tuple(_key(r.get(_member(cfg.view, d))) for d in dims): _number(
                    r.get(_member(cfg.view, comparison.measure))
                )
                for r in cube.load(query)
            }
            sql = {
                tuple(_key(r[d]) for d in dims): _number(r["value"])
                for r in wh.rows(
                    wrap_cube(bound, cfg.view, dims, set(), comparison.measure)
                )
            }
            label = f"{comparison.id} {cut_label(cut)}" + (
                f" by {', '.join(dims)}" if dims else " total"
            )
            bad = [
                f"{label} {k}: API {api.get(k)}, SQL {sql.get(k)}"
                for k in sorted(api.keys() | sql.keys())
                if not _same(api.get(k), sql.get(k))
            ]
            disagreements += bad
            print(f"{label}: {len(api)} rows, {'agree' if not bad else 'disagree'}.")
        last = clock()
        changed = changed_between(wh, sorted(tables), first, last)

    if changed:
        raise Refusal(f"{', '.join(changed)} rebuilt while the check ran; run it again")
    if disagreements:
        raise Refusal(
            "Cube's API and its compiled SQL disagree:\n  " + "\n  ".join(disagreements)
        )
    print(
        f"Cube's API and its compiled SQL agree on {len(picks)} of {len(picks)} "
        f"checks at {API_DECIMALS} decimals."
    )


# --- prove -------------------------------------------------------------------


def _sheet_columns(twb_xml: str, sheet: str) -> list[ET.Element]:
    root = ET.fromstring(twb_xml)
    ws = next((w for w in root.iter("worksheet") if w.get("name") == sheet), None)
    if ws is None:
        raise Refusal(f"the workbook has no worksheet {sheet!r}")
    return [
        col
        for deps in ws.iter("datasource-dependencies")
        for col in deps.findall("column")
    ]


def _bare(name: str) -> str:
    return name[1:-1] if name.startswith("[") and name.endswith("]") else name


def _export_columns(
    comparison: Comparison,
    headers: list[str],
    columns: list[ET.Element],
    value_column: str | None,
) -> tuple[dict[str, str], str]:
    """Map export headers to dashboard dim names, and pick the value header."""
    lower = {h.lower(): h for h in headers}
    mapping: dict[str, str] = {}
    for dim in comparison.dims:
        names = {dim.dashboard}
        names |= {
            caption
            for caption, pair in comparison.filters.items()
            if pair.dashboard == dim.dashboard
        }
        names |= {
            col.get("caption") or ""
            for col in columns
            if _bare(col.get("name") or "") == dim.dashboard
        }
        found = [lower[n.lower()] for n in names if n and n.lower() in lower]
        if not found:
            raise Refusal(
                f"no export column for dim {dim.dashboard!r}; "
                f"the export has {', '.join(headers)}"
            )
        mapping[found[0]] = dim.dashboard
    rest = [h for h in headers if h not in mapping]
    if value_column:
        if value_column not in rest:
            raise Refusal(
                f"--value-column {value_column!r} is not an export column; "
                f"choose from {', '.join(rest)}"
            )
        return mapping, value_column
    if len(rest) != 1:
        raise Refusal(
            f"the export has {len(rest)} columns besides the dims "
            f"({', '.join(rest)}); name the one to compare with --value-column"
        )
    return mapping, rest[0]


def prove(
    cfg: ViewConfig,
    path: Path,
    comparison_id: str,
    *,
    wh: Warehouse,
    tbl: tableau.Tableau,
    now: datetime,
    max_usd: float,
    value_column: str | None,
) -> tableau.Proof:
    """Prove a comparison's probe against the sheet and write `proof:`.

    Failures and browser cuts print to the terminal only.

    Raises:
        Refusal: The comparison is unknown or incomplete, an exportable cut
            has no rows on a side, or the proof failed.
    """
    comparison = next((c for c in cfg.comparisons if c.id == comparison_id), None)
    if comparison is None:
        raise Refusal(f"{path}: no comparison {comparison_id!r}")
    _require(comparison, "workbook", "sheet", "dashboard_view", "decimals")
    workbook, sheet = comparison.workbook or "", comparison.sheet or ""

    twb = tbl.download_twb(workbook)
    columns = _sheet_columns(twb, sheet)
    measures = [c.get("name") or "" for c in columns if c.get("role") == "measure"]
    if not measures:
        raise Refusal(f"sheet {sheet!r} lists no measure")
    exportable, browser = tableau.split_cuts(_cuts(comparison), twb)
    if not exportable:
        raise Refusal(f"comparison {comparison.id!r} has no cut a REST export can take")

    snap = tbl.capture(
        workbook,
        sheet,
        exportable,
        lambda x: tableau.drop_number_formats(x, measures),
    )
    if snap.refresh_started < now - PROOF_WINDOW:
        raise Refusal(
            f"the extract refreshed at {snap.refresh_started}, outside the 7 days "
            "of warehouse history; prove after the next refresh"
        )

    exports: list[dict] = []
    probes: list[dict] = []
    with wh.budget(max_usd):
        for cut, rows in zip(exportable, snap.exports, strict=True):
            label = cut_label(cut)
            probe_rows = wh.rows(
                as_of(probe_sql(cfg, comparison, cut), snap.refresh_started, wh).sql
            )
            if not rows or not probe_rows:
                side = "export" if not rows else "probe"
                raise Refusal(f"cut {label}: the {side} has no rows")
            mapping, value = _export_columns(
                comparison, list(rows[0]), columns, value_column
            )
            exports += [
                {
                    **{d: r[h] for h, d in mapping.items()},
                    "value": r[value],
                    "cut": label,
                }
                for r in rows
            ]
            probes += [
                {
                    **{d.dashboard: r[d.dashboard] for d in comparison.dims},
                    "value": r["value"],
                    "cut": label,
                }
                for r in probe_rows
            ]

    proof = tableau.prove(comparison, exports, probes, twb_xml=twb, now=now)
    for cut in browser:
        print(f"Prove in the browser: {cut_label(cut)}")
    if not proof.proven:
        print(f"Proof failed for {comparison.id} ({proof.cells} cells matched):")
        for failure in proof.failures:
            print(f"  {failure}")
        raise Refusal(f"comparison {comparison.id!r} is not proven; nothing written")

    write_proof(
        path,
        comparison.id,
        {
            "fingerprint": proof.fingerprint,
            "cells": proof.cells,
            "proven_at": proof.proven_at.isoformat(),
            "workbook_updated_at": tbl.workbook_updated(workbook).isoformat(),
        },
    )
    print(f"Proved {comparison.id}: {proof.cells} cells; wrote proof to {path}.")
    return proof


def prove_check(cfg: ViewConfig, *, tbl: tableau.Tableau) -> list[str]:
    """List comparisons whose workbook was published after their proof."""
    stale = []
    for comparison in cfg.comparisons:
        if not comparison.workbook:
            continue
        proof = comparison.proof
        if proof is None:
            stale.append(f"{comparison.id}: not proven")
            continue
        updated = tbl.workbook_updated(comparison.workbook)
        if not proof.workbook_updated_at:
            stale.append(f"{comparison.id}: proof has no workbook_updated_at; re-prove")
        elif updated > datetime.fromisoformat(proof.workbook_updated_at):
            stale.append(
                f"{comparison.id}: workbook published {updated.isoformat()}, after "
                f"the proof's {proof.workbook_updated_at}; re-prove"
            )
    for line in stale:
        print(line)
    if not stale:
        print("Every proof is current.")
    return stale


# --- discover ----------------------------------------------------------------


def _measure_expression(sql: str, view: str, measure: str) -> str:
    """The SELECT expression of a measure-only compiled query, alias dropped."""
    head = re.split(r"\bFROM\b", sql, maxsplit=1, flags=re.IGNORECASE)[0]
    head = re.sub(r"^\s*SELECT\s+", "", head, flags=re.IGNORECASE)
    return head.replace(f"`{view}__{measure}`", "").strip()


def discover(
    cfg: ViewConfig,
    measure: str,
    *,
    cube: Cube,
    tbl: tableau.Tableau,
    exposures_path: Path,
    only: list[str],
) -> list[finder.Candidate]:
    """Print each workbook's calculated fields ranked against a measure."""
    compiled = cube.compiled({"measures": [_member(cfg.view, measure)]})
    member_sql = _measure_expression(compiled.sql, cfg.view, measure)

    exposures = finder.tableau_exposures(exposures_path)
    if exposures.skipped:
        print(
            f"Skipped exposures without a luid or models: {', '.join(exposures.skipped)}"
        )

    found: list[finder.Candidate] = []
    for exposure in exposures:
        if only and exposure.name not in only:
            continue
        if not exposure.luid:
            print(f"Skipped {exposure.name}: empty luid")
            continue
        try:
            twb = tbl.download_twb(exposure.luid)
        except (
            TSC.ServerResponseError,
            zipfile.BadZipFile,
            ValueError,
            OSError,
        ) as exc:
            print(f"Could not read {exposure.label}: {type(exc).__name__}: {exc}")
            continue
        found += finder.rank(
            measure,
            member_sql,
            finder.calculated_fields(twb),
            workbook_luid=exposure.luid,
            workbook_label=exposure.label,
        )

    found.sort(key=lambda c: (-c.score, c.workbook_label, c.caption))
    if not found:
        print(f"No candidates for {measure}.")
    for c in found:
        formula = " ".join(c.formula.split())
        print(
            f"{c.score:.2f}  {c.workbook_label} ({c.workbook_luid})  "
            f"{c.caption!r} on {', '.join(c.worksheets) or 'no sheet'}: {formula}"
        )
    return found


def utc(value: str) -> datetime:
    """Parse an ISO moment; naive input is refused, aware input kept."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{value!r} has no time zone; add Z or an offset")
    return parsed.astimezone(timezone.utc)
