"""What each command does, wired from the other modules.

`cli.py` parses arguments and builds the clients; the functions here take those
clients as arguments so tests can pass fakes. The dashboard side is read as of
a fact build's start and Cube as of its end. Every BigQuery query runs inside
`Warehouse.budget`, and only aggregates come back: row-level comparisons run
inside BigQuery through `compare.reconcile_sql`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re

# trunk-ignore(bandit/B405): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
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
from .compare import Gap, Group
from .config import ColumnPair, Comparison, Decision, ViewConfig, write_proof
from .cube_client import (
    Compiled,
    Cube,
    bind,
    drop_limit,
    network_schools,
    refuse_unless_safe,
    sort_school_filters,
)
from .decisions import Applied
from .moment import WINDOW, Build, changed_between, fact_builds, pick_moment
from .report import MeasureResult, RunResult
from .timetravel import PROJECT, AsOf, as_of, repin, utc_literal

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


_SQL_COMPARE = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
# How a run result names each Cube scope operator.
_SCOPE_WORDS = {"equals": "in", "notEquals": "not in", **_SQL_COMPARE}


def _dashboard_filter_sql(entry: dict[str, Any]) -> str:
    """One `dashboard_filters` entry as SQL; `not_equals` keeps nulls, as Cube's does."""
    column, operator = entry["dashboard"], entry["operator"]
    if operator == "set":
        return f"{column} IS NOT NULL"
    if operator in _SQL_COMPARE:
        return f"{column} {_SQL_COMPARE[operator]} {_lit(entry['values'][0])}"
    match = _column_predicate(column, entry["values"])
    return match if operator == "equals" else f"({column} IS NULL OR NOT {match})"


def dashboard_predicate(comparison: Comparison, cut: dict[str, Any]) -> str:
    """Return the WHERE predicate a cut puts on the dashboard rows.

    It ends with the comparison's `dashboard_filters`, which Cube never sees.
    """
    parts = [
        _column_predicate(comparison.filters[caption].dashboard, value)
        for caption, value in effective_filters(comparison, cut).items()
    ] + [_dashboard_filter_sql(e) for e in comparison.dashboard_filters]
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
        # trunk-ignore(bandit/B608): identifiers are validated in config.py and values are bound or literal-escaped
        f"SELECT {', '.join(cols)} FROM {_dashboard_ref(comparison)} "
        f"WHERE {_any_cut_predicate(comparison)}"
    )


def probe_sql(cfg: ViewConfig, comparison: Comparison, cut: dict[str, Any]) -> str:
    """Return the probe over the dashboard rows under one cut, before time travel.

    `probe` is an aggregate over the rows; `probe_sql` is a template whose
    `{rows}`, `{where}` and `{dims}` are filled here.
    """
    # trunk-ignore(bandit/B608): identifiers are validated in config.py and values are bound or literal-escaped
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
        # trunk-ignore(bandit/B608): identifiers are validated in config.py and values are bound or literal-escaped
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
    # trunk-ignore(bandit/B608): SQL text comes from Cube's compiled query; identifiers validated in config.py
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


def _by_key(rows: Iterable[dict], key, value, where: str) -> dict:
    """Index rows by cell key, refusing 2 rows that land on one cell."""
    out: dict = {}
    for r in rows:
        k = key(r)
        if k in out:
            raise Refusal(
                f"{where}: 2 rows share the cell {', '.join(k) or '(total)'}; "
                "the dims do not pick out one cell"
            )
        out[k] = value(r)
    return out


def _cells(
    comparison: Comparison,
    cut: dict[str, Any],
    dash_rows: list[dict],
    cube_rows: list[dict],
    decimals: int,
) -> list[Cell]:
    where = f"{comparison.id} {cut_label(cut)}"
    dash = _by_key(
        dash_rows,
        lambda r: tuple(_key(r[d.dashboard]) for d in comparison.dims),
        lambda r: _number(r["value"]),
        f"{where} dashboard",
    )
    cube = _by_key(
        cube_rows,
        lambda r: tuple(_key(r[d.cube]) for d in comparison.dims),
        lambda r: _number(r["value"]),
        f"{where} Cube",
    )
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


def probe_fingerprint(cfg: ViewConfig, comparison: Comparison) -> str:
    """Fingerprint the probe a proof covers: the default cut's probe SQL.

    It covers the probe text, dims, defaults and dashboard view; `run` refuses
    a proof whose probe has changed since.
    """
    base = decisions.sql_fingerprint(probe_sql(cfg, comparison, {}))
    # How the export is read is part of what a proof covers. Unset keys add
    # nothing, so a proof written before them keeps its fingerprint.
    extras = [f"sheet_field={comparison.sheet_field}"] if comparison.sheet_field else []
    if comparison.split_rows != "refuse":
        extras.append(f"split_rows={comparison.split_rows}")
    if not extras:
        return base
    return hashlib.sha256("\n".join([base, *extras]).encode()).hexdigest()


def _as_of(sql: str, ts: datetime, wh: Warehouse) -> AsOf:
    """`as_of`, with its fail-closed refusals (an unknown table, a deep view)."""
    try:
        return as_of(sql, ts, wh)
    except ValueError as exc:
        raise Refusal(f"cannot read the SQL as of {utc_literal(ts)}: {exc}") from exc


def _masked(at: AsOf, ts: datetime) -> str:
    """The expanded SQL with the moment taken out, so only definitions remain."""
    return at.sql.replace(utc_literal(ts), "<moment>")


@dataclasses.dataclass
class _Sides:
    """What a run collects across comparisons."""

    cube_tables: set[str] = dataclasses.field(default_factory=set)
    live: set[str] = dataclasses.field(default_factory=set)
    cells: list[Cell] = dataclasses.field(default_factory=list)
    groups: list[Group] = dataclasses.field(default_factory=list)
    clauses: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    sql: dict[str, tuple[str, str]] = dataclasses.field(default_factory=dict)
    fingerprints: dict[str, dict[str, str]] = dataclasses.field(default_factory=dict)
    moved: dict[str, bool] = dataclasses.field(default_factory=dict)


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
    """Compare one comparison's cells and rows, and fingerprint both sides.

    The fingerprints hash the SQL each side runs, expanded through every view
    as of the moment and with the moment masked: a view or member edit asks
    its decisions to be re-confirmed, a new moment does not.
    """
    dates = _date_cubes(cfg)
    dims = [d.cube for d in comparison.dims]
    compiled: dict[tuple[str, bool], str] = {}
    expanded: dict[tuple[str, datetime], AsOf] = {}

    def cube_sql(query: dict, rows: bool = False) -> str:
        key = (json.dumps(query, sort_keys=True), rows)
        if key not in compiled:
            compiled[key] = _cube_sql(cfg, cube, query, schools, rows=rows)
        return compiled[key]

    def at(sql: str, ts: datetime) -> AsOf:
        if (sql, ts) not in expanded:
            expanded[(sql, ts)] = _as_of(sql, ts, wh)
        return expanded[(sql, ts)]

    for cut in _cuts(comparison):
        cube_at = at(cube_sql(cell_query(cfg.view, comparison, cut)), build.end)
        dash_at = at(probe_sql(cfg, comparison, cut), build.start)
        sides.cube_tables |= cube_at.tables
        sides.live |= cube_at.live | dash_at.live
        cube_rows = wh.rows(
            wrap_cube(cube_at.sql, cfg.view, dims, dates, comparison.measure)
        )
        dash_rows = wh.rows(dash_at.sql)
        sides.cells += _cells(
            comparison, cut, dash_rows, cube_rows, comparison.decimals or 0
        )

    cube_parts = [
        _masked(
            at(cube_sql(cell_query(cfg.view, comparison, {})), build.end), build.end
        )
    ]
    dash_parts = [_masked(at(probe_sql(cfg, comparison, {}), build.start), build.start)]

    if comparison.rows is not None:
        cube_at = at(cube_sql(row_query(cfg.view, comparison), rows=True), build.end)
        dash_at = at(dashboard_rows_sql(cfg, comparison), build.start)
        sides.cube_tables |= cube_at.tables
        sides.live |= cube_at.live | dash_at.live
        cube_parts.append(_masked(cube_at, build.end))
        dash_parts.append(_masked(dash_at, build.start))
        columns = _unique(p.cube for p in _row_pairs(comparison))
        shared = sorted(cube_at.tables & dash_at.tables)
        unknown = [t for t in shared if t not in sides.moved]
        changed = set(changed_between(wh, unknown, build.start, build.end))
        sides.moved |= {t: t in changed for t in unknown}
        if moved := [t for t in shared if sides.moved[t]]:
            raise Refusal(
                f"comparison {comparison.id!r}: both sides read {', '.join(moved)}, "
                "which changed during the build; BigQuery reads a table at 1 "
                "moment per query, so the rows cannot be reconciled at this build"
            )
        # Unchanged between start and end, so the Cube side reads its shared
        # tables at the start: BigQuery refuses 1 table at 2 moments.
        cube_rows_sql = repin(cube_at.sql, shared, build.end, build.start)
        result = wh.rows(
            compare.reconcile_sql(
                wrap_cube(cube_rows_sql, cfg.view, columns, dates, None),
                dash_at.sql,
                comparison.rows,
                comparison.dims,
            )
        )
        sides.groups += compare.groups_from(comparison.id, result)
        sides.sql[comparison.id] = (dash_at.sql, cube_at.sql)

    sides.fingerprints[comparison.id] = {
        "cube": decisions.sql_fingerprint(sort_school_filters("\n".join(cube_parts))),
        "dashboard": decisions.sql_fingerprint("\n".join(dash_parts)),
    }


def _clauses(comparison: Comparison, groups: list[Group], sides: _Sides) -> list[str]:
    if comparison.id not in sides.sql:
        return []
    by_cube = {d.cube: d.dashboard for d in comparison.dims}
    columns = _unique(
        name
        for g in groups
        if g.comparison_id == comparison.id
        for column, _ in g.dims
        for name in (column, by_cube.get(column, column))
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


def _priced_load(cube: Cube, wh: Warehouse, query: dict) -> list[dict]:
    """`Cube.load`, after a dry run of the SQL Cube compiles for the same query.

    Cube runs that SQL in BigQuery, so call this inside `wh.budget`: the price
    counts toward the cap before the load runs, and toward `wh.spent`.
    """
    wh.price(bind(cube.compiled(query)))
    return cube.load(query)


def _load_value(cube: Cube, wh: Warehouse, query: dict, member: str) -> float | None:
    rows = _priced_load(cube, wh, query)
    if not rows or rows[0].get(member) is None:
        return None
    return float(rows[0][member])


def _anchors_and_identities(
    cfg: ViewConfig, cube: Cube, wh: Warehouse, comparisons: list[Comparison]
) -> tuple[list[Finding], dict[str, list[CheckResult]]]:
    """Run anchors and identities through `Cube.load` on current data.

    Each load is priced first, so call this inside `wh.budget`.
    """
    findings: list[Finding] = []
    results: dict[str, list[CheckResult]] = {}

    for anchor in cfg.anchors:
        # load_view_config requires time_dimension whenever anchors are set.
        value = _load_value(
            cube,
            wh,
            checks.anchor_query(anchor, cfg.view, cfg.time_dimension or ""),
            _member(cfg.view, anchor.measure),
        )
        findings.append(
            checks.anchor_finding(anchor, float("nan") if value is None else value)
        )
        results.setdefault(anchor.measure, []).append(CheckResult("anchor", False))

    for identity in cfg.identities:
        for cut in _identity_cuts(cfg, comparisons):
            query = checks.identity_query(identity, cut, cfg.view)
            rows = _priced_load(cube, wh, query)
            row = rows[0] if rows else {}
            # One row holds both sides; `right` reads only the names it uses.
            values = {
                m.split(".", 1)[1]: _number(row.get(m)) for m in query["measures"]
            }
            # trunk-ignore(pyright/reportArgumentType): identity_finding fails a None side
            finding = checks.identity_finding(identity, values[identity.left], values)
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
    open_groups: list[Group],
    open_gaps: list[Gap],
) -> list[MeasureResult]:
    """The verdict reads cells only; open groups and gaps are counted beside it."""
    results: dict[str, list[CheckResult]] = {}
    counts: dict[str, Counter] = {}
    measure_of = {c.id: c.measure for c in comparisons}
    for comparison in comparisons:
        mine = [c for c in cells if c.comparison == comparison.id]
        passed = bool(mine) and all(c.verdict == "pass" for c in mine)
        results.setdefault(comparison.measure, []).append(
            CheckResult("dashboard", passed)
        )
        counts.setdefault(comparison.measure, Counter()).update(c.verdict for c in mine)
    for measure, found in other.items():
        results.setdefault(measure, []).extend(found)
    groups = Counter(measure_of.get(g.comparison_id) for g in open_groups)
    gaps = Counter(
        measure
        for g in open_gaps
        for measure in {measure_of.get(c) for c in g.comparisons}
    )
    return [
        MeasureResult(
            measure,
            checks.strongest_check(measure, found),
            checks.verdict(found),
            dict(counts.get(measure, {})),
            groups.get(measure, 0),
            gaps.get(measure, 0),
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


def _proof_is_old(proven_at: str, now: datetime) -> bool:
    """True when a proof is more than 7 days old, or its time is unreadable."""
    try:
        proven = datetime.fromisoformat(proven_at)
    except ValueError:
        return True
    if proven.tzinfo is None:
        proven = proven.replace(tzinfo=timezone.utc)
    return now - proven > WINDOW


def _browser_cuts(comparisons: list[Comparison]) -> list[str]:
    """Cuts no proof's REST export covered: parameter cuts, and cuts added since.

    A proof written before proofs recorded their cuts cannot say which it
    covered, so the comparison is listed for a re-prove.
    """
    out = []
    for comparison in comparisons:
        recorded = comparison.proof.cuts if comparison.proof else None
        if recorded is None:
            out.append(
                f"{comparison.id}: cuts unknown (the proof records none); re-prove"
            )
            continue
        out += [
            f"{comparison.id}: {cut_label(cut)} (no export proved it)"
            for cut in _cuts(comparison)
            if cut_label(cut) not in recorded
        ]
    return out


def _unproven_totals(comparisons: list[Comparison]) -> list[str]:
    """Comparisons whose proof skipped the export's total rows, or cannot say."""
    out = []
    for comparison in comparisons:
        skipped = comparison.proof.totals_skipped if comparison.proof else None
        if skipped is None:
            out.append(
                f"{comparison.id}: totals not proven: unknown (the proof records "
                "no count); re-prove"
            )
        elif skipped > 0:
            out.append(f"{comparison.id}: totals not proven: {skipped} rows")
    return out


def _gaps(comparisons: list[Comparison]) -> tuple[list[Gap], list[str]]:
    """Missing cuts and filters across the proofs, one per kind and field.

    Also lists each comparison whose proof predates them.
    """
    found: dict[tuple[str, str], dict[str, Any]] = {}
    unknown = []
    for comparison in comparisons:
        proof = comparison.proof
        if proof is None or proof.missing_cuts is None or proof.missing_filters is None:
            unknown.append(
                f"{comparison.id}: missing cuts and filters unknown (the proof "
                "predates them); re-prove"
            )
            continue
        restricting = set(proof.restricting_filters or [])
        for kind, names in (
            ("cut", proof.missing_cuts),
            ("filter", proof.missing_filters),
        ):
            for name in names:
                entry = found.setdefault(
                    (kind, name),
                    {"sheets": [], "comparisons": [], "restricting": False},
                )
                if comparison.sheet and comparison.sheet not in entry["sheets"]:
                    entry["sheets"].append(comparison.sheet)
                entry["comparisons"].append(comparison.id)
                entry["restricting"] |= kind == "filter" and name in restricting
    gaps = [
        Gap(kind, name, tuple(e["sheets"]), tuple(e["comparisons"]), e["restricting"])
        for (kind, name), e in sorted(found.items())
    ]
    return gaps, unknown


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
        Refusal: A confirmed comparison has no proof, its probe changed
            since the proof, or it lacks a key it needs.
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
    changed_probes = [
        c.id
        for c in comparisons
        if c.proof and c.proof.probe_fingerprint != probe_fingerprint(cfg, c)
    ]
    if changed_probes:
        raise Refusal(
            f"comparison {', '.join(map(repr, changed_probes))}: the probe is not "
            "the one its proof covers; run `prove` again"
        )
    for comparison in comparisons:
        if comparison.proof:
            print(f"Proof for {comparison.id}: proven {comparison.proof.proven_at}.")
            if _proof_is_old(comparison.proof.proven_at, now):
                print(
                    f"Warning: the proof for {comparison.id} is more than 7 days "
                    "old. `run` never reads the workbook, so run `prove --check` "
                    "to catch an edit since."
                )

    totals = _unproven_totals(comparisons)
    for line in totals:
        print(f"{line}.")

    with wh.budget(max_usd):
        builds = fact_builds(wh, cfg.fact, since=now - WINDOW)
        build = pick_moment(builds, now, requested, cfg.fact)
        schools = network_schools(wh)
        sides = _Sides()
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
        findings, other = _anchors_and_identities(cfg, cube, wh, comparisons)
        cost = wh.spent

    gaps, gaps_unknown = _gaps(comparisons)
    try:
        applied = decisions.apply(
            cfg.decisions, sides.groups, sides.fingerprints, gaps=gaps
        )
    except ValueError as exc:
        raise Refusal(str(exc)) from exc

    clauses = {c.id: _clauses(c, applied.open, sides) for c in comparisons}
    result = RunResult(
        view=cfg.view,
        moment=build,
        measures=_measures(
            comparisons, sides.cells, other, applied.open, applied.open_gaps
        ),
        applied=applied,
        findings=findings,
        live_sources=sorted(sides.live),
        changed_dims=changed,
        scopes=[
            f"{c.id}: {f['member']} is set"
            if f["operator"] == "set"
            else (
                f"{c.id}: {f['member']} {_SCOPE_WORDS[f['operator']]} "
                f"{', '.join(map(str, f['values']))}"
            )
            for c in comparisons
            for f in _scope_cube_filters(cfg.view, c)
        ],
        dashboard_filters=[
            f"{c.id}: {_dashboard_filter_sql(e)}"
            for c in comparisons
            for e in c.dashboard_filters
        ],
        cost_usd=cost,
        proofs={c.id: c.proof.proven_at for c in comparisons if c.proof},
        browser_cuts=_browser_cuts(comparisons),
        totals=totals,
        clauses={k: v for k, v in clauses.items() if v},
        fingerprints=sides.fingerprints,
        decisions_fingerprint=decisions.decisions_fingerprint(cfg.decisions),
        gaps_unknown=gaps_unknown,
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


def _group(data: dict) -> Group:
    """JSON stores `dims` as lists; a group compares by tuples."""
    return Group(**{**data, "dims": tuple(tuple(d) for d in data["dims"])})


def _gap(data: dict) -> Gap:
    return Gap(
        **{
            **data,
            "sheets": tuple(data["sheets"]),
            "comparisons": tuple(data["comparisons"]),
        }
    )


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
            open=[_group(g) for g in applied["open"]],
            quiet=[(Decision(**d), _group(g)) for d, g in applied["quiet"]],
            reconfirm=[Decision(**d) for d in applied["reconfirm"]],
            no_longer_needed=[Decision(**d) for d in applied["no_longer_needed"]],
            partly_stale=[
                (Decision(**d), list(v)) for d, v in applied.get("partly_stale", [])
            ],
            open_gaps=[_gap(g) for g in applied.get("open_gaps", [])],
            quiet_gaps=[
                (Decision(**d), _gap(g)) for d, g in applied.get("quiet_gaps", [])
            ],
        ),
        findings=[Finding(**f) for f in data["findings"]],
        live_sources=data["live_sources"],
        changed_dims=data["changed_dims"],
        scopes=data["scopes"],
        cost_usd=data["cost_usd"],
        proofs=data["proofs"],
        browser_cuts=data["browser_cuts"],
        totals=data.get("totals", []),
        clauses=data["clauses"],
        fingerprints=data.get("fingerprints", {}),
        decisions_fingerprint=data.get("decisions_fingerprint", ""),
        gaps_unknown=data.get("gaps_unknown", []),
        dashboard_filters=data.get("dashboard_filters", []),
    )


# --- review ------------------------------------------------------------------


def review(configs: list[ViewConfig], domain: str, cache_root: Path) -> str:
    """Return the review-issue body from each view's latest saved run.

    The latest run is the `run.json` written last, whatever moment it read.
    Reads only the local cache; nothing is posted.

    Raises:
        Refusal: A view has no saved run, its saved run is in a shape this
            validator cannot read, or its decisions changed since the run (a
            run saved before runs recorded them counts as changed).
    """
    runs = []
    for cfg in configs:
        saved = sorted(
            (cache_root / cfg.view).glob("*/run.json"), key=lambda p: p.stat().st_mtime
        )
        if not saved:
            raise Refusal(f"{cfg.view}: no saved run; `run` it first")
        try:
            run_result = _run_from_json(json.loads(saved[-1].read_text()))
        except (KeyError, TypeError) as exc:
            raise Refusal(
                f"{cfg.view}: the saved run {saved[-1]} was written by an older "
                "validator; `run` it again"
            ) from exc
        if run_result.decisions_fingerprint != decisions.decisions_fingerprint(
            cfg.decisions
        ):
            raise Refusal(
                f"{cfg.view}: the decisions changed since the saved run "
                f"{saved[-1]}; `run` it again"
            )
        runs.append(run_result)
    definitions = {
        cfg.view: {c.id: c.definitions for c in cfg.comparisons if c.definitions}
        for cfg in configs
    }
    return report.render_review_issue(domain, runs, definitions)


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
            tables |= _as_of(bound, first, wh).tables
            dims = [d.cube for d in comparison.dims] if with_dims else []
            # The load runs this SQL in BigQuery, so it is priced like the rest.
            wh.price(bound)
            label = f"{comparison.id} {cut_label(cut)}" + (
                f" by {', '.join(dims)}" if dims else " total"
            )
            api = _by_key(
                cube.load(query),
                lambda r, dims=dims: tuple(
                    _key(r.get(_member(cfg.view, d))) for d in dims
                ),
                lambda r, m=comparison.measure: _number(r.get(_member(cfg.view, m))),
                f"{label} API",
            )
            sql = _by_key(
                wh.rows(wrap_cube(bound, cfg.view, dims, set(), comparison.measure)),
                lambda r, dims=dims: tuple(_key(r[d]) for d in dims),
                lambda r: _number(r["value"]),
                f"{label} SQL",
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
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
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
    field = comparison.sheet_field
    if field:
        if field not in rest:
            raise Refusal(
                f"sheet_field {field!r} is not an export column; "
                f"the export has {', '.join(rest)}"
            )
        return mapping, field
    if len(rest) != 1:
        raise Refusal(
            f"the export has {len(rest)} columns besides the dims "
            f"({', '.join(rest)}); name the one to compare with sheet_field"
        )
    return mapping, rest[0]


MEASURE_NAMES, MEASURE_VALUES = "Measure Names", "Measure Values"


def long_to_wide(rows: list[dict[str, str]], field: str | None) -> list[dict[str, str]]:
    """Keep one field of a long export as its own column.

    A sheet with `Measure Names` on a shelf exports one row per field, naming
    it in `Measure Names` and holding it in `Measure Values`. A wide export
    comes back as is.

    Raises:
        Refusal: The export is long and `field` is unset or names no field in
            it; the message lists the fields it has.
    """
    if not rows or MEASURE_NAMES not in rows[0]:
        return rows
    names = ", ".join(sorted({r[MEASURE_NAMES] for r in rows}))
    if not field:
        raise Refusal(
            f"the export has one row per field; set sheet_field to one of {names}"
        )
    kept = [
        {
            **{k: v for k, v in r.items() if k not in (MEASURE_NAMES, MEASURE_VALUES)},
            field: r[MEASURE_VALUES],
        }
        for r in rows
        if r[MEASURE_NAMES] == field
    ]
    if not kept:
        raise Refusal(f"sheet_field {field!r} is not in the export; it has {names}")
    return kept


@dataclasses.dataclass(frozen=True)
class SheetGaps:
    """Sheet fields with no Cube member, by caption. Values are never read."""

    cuts: list[str]
    filters: list[str]
    restricting: list[str]


def sheet_gaps(twb_xml: str, comparison: Comparison) -> SheetGaps:
    """Name the sheet's cuts and filters that have no Cube member.

    A field counts as having one when the comparison maps it anywhere: a dim,
    a filter, or a row grain or value. Aggregated fields, `Measure Names`,
    user filters and fields built on the viewer's identity are skipped.
    """
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    ws = finder.worksheet(ET.fromstring(twb_xml), comparison.sheet or "")
    if ws is None:
        raise Refusal(f"the workbook has no worksheet {comparison.sheet!r}")
    pairs = [*comparison.dims, *comparison.filters.values()]
    if comparison.rows:
        pairs += [*comparison.rows.grain, *comparison.rows.values]
    mapped = {p.dashboard for p in pairs}
    mapped_captions = set(comparison.filters)
    caption, personal = finder.sheet_fields(ws)

    def field_of(ref: str) -> str | None:
        m = finder.FIELD_REF.search(ref)
        if m is None or m["deriv"] in finder.AGGREGATES:
            return None
        name = m["name"]
        if name in mapped or name in personal or caption.get(name) in mapped_captions:
            return None
        return name

    shelves = " ".join(
        [el.text or "" for el in ws.iter() if el.tag in ("rows", "cols")]
        + [el.get("column") or "" for enc in ws.iter("encodings") for el in enc]
    )
    cuts = {f for ref in finder.FIELD_REF.finditer(shelves) if (f := field_of(ref[0]))}
    filters: set[str] = set()
    restricting: set[str] = set()
    for filter_el in ws.iter("filter"):
        name = field_of(filter_el.get("column") or "")
        if name is None or name in cuts:
            continue
        filters.add(name)
        if finder.restricts(filter_el):
            restricting.add(name)

    def captions(names: set[str]) -> list[str]:
        return sorted({caption.get(n, n) for n in names})

    return SheetGaps(captions(cuts), captions(filters), captions(restricting))


TOTAL_LABEL = "All"


def _alias_keys(columns: list[ET.Element], dim: str) -> dict[str, str]:
    """Map each alias a sheet displays for a dim back to the stored value.

    A string key is stored quoted (`"Camden"`); the quotes are dropped.
    """
    out: dict[str, str] = {}
    for col in columns:
        if _bare(col.get("name") or "") != dim:
            continue
        for alias in col.iter("alias"):
            key, shown = alias.get("key") or "", alias.get("value") or ""
            if len(key) > 1 and key[0] == key[-1] == '"':
                key = key[1:-1]
            out[shown] = key
    return out


def _export_cells(
    comparison: Comparison,
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    value: str,
    columns: list[ET.Element],
    probe_rows: list[dict],
) -> tuple[list[dict], int, int]:
    """Turn export rows into probe-shaped cells; count total and summed rows.

    An export shows a dim's alias (grade 0 as `K`), so each value goes back
    through the sheet's aliases. A sheet with totals exports them as rows whose
    dim reads `All`; those are dropped, unless the probe has a real `All`
    member for that dim. With `split_rows: sum`, rows that share every mapped
    dim (split by a sheet field Cube lacks) are added into one cell; blanks are
    skipped, and a cell of blanks stays blank.
    """
    aliases = {d.dashboard: _alias_keys(columns, d.dashboard) for d in comparison.dims}
    real_all = {
        d.dashboard
        for d in comparison.dims
        if any(str(r[d.dashboard]) == TOTAL_LABEL for r in probe_rows)
    }
    cells: list[dict] = []
    totals = 0
    for r in rows:
        dims = {d: r[h] for h, d in mapping.items()}
        if any(v == TOTAL_LABEL and d not in real_all for d, v in dims.items()):
            totals += 1
            continue
        dims = {d: aliases[d].get(v, v) for d, v in dims.items()}
        cells.append({**dims, "value": r[value]})
    if comparison.split_rows != "sum":
        return cells, totals, 0
    merged: dict[tuple, dict] = {}
    sums: dict[tuple, Decimal | None] = {}
    for cell in cells:
        key = tuple(cell[d.dashboard] for d in comparison.dims)
        merged.setdefault(key, cell)
        text = str(cell["value"]).strip()
        if not text:
            sums.setdefault(key, None)
            continue
        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise Refusal(f"cannot add export value {text!r}") from exc
        sums[key] = (sums.get(key) or Decimal(0)) + number
    out = []
    for k, cell in merged.items():
        total = sums[k]
        out.append(
            {**cell, "value": "" if total is None else format(total.normalize(), "f")}
        )
    return out, totals, len(cells) - len(out)


def _comparison_by_id(cfg: ViewConfig, path: Path, comparison_id: str) -> Comparison:
    comparison = next((c for c in cfg.comparisons if c.id == comparison_id), None)
    if comparison is None:
        raise Refusal(f"{path}: no comparison {comparison_id!r}")
    return comparison


def _capture(
    comparison: Comparison,
    tbl: tableau.Tableau,
    captures: dict[tuple, tableau.Snapshot] | None,
) -> tuple[str, list[ET.Element], list[dict], list[dict], tableau.Snapshot]:
    """Export a comparison's sheet once per (workbook, sheet, cuts).

    Returns:
        The workbook XML, the sheet's columns, the cuts a REST export takes,
        the cuts only a browser can prove, and the snapshot.
    """
    _require(comparison, "workbook", "sheet")
    workbook, sheet = comparison.workbook or "", comparison.sheet or ""
    twb = tbl.download_twb(workbook)
    columns = _sheet_columns(twb, sheet)
    measures = [c.get("name") or "" for c in columns if c.get("role") == "measure"]
    if not measures:
        raise Refusal(f"sheet {sheet!r} lists no measure")
    exportable, browser = tableau.split_cuts(_cuts(comparison), twb)
    if not exportable:
        raise Refusal(f"comparison {comparison.id!r} has no cut a REST export can take")
    captures = {} if captures is None else captures
    key = (workbook, sheet, tuple(cut_label(cut) for cut in exportable))
    if key not in captures:
        try:
            captures[key] = tbl.capture(
                workbook,
                sheet,
                exportable,
                lambda x: tableau.expose_sheet(
                    tableau.drop_number_formats(x, measures), sheet
                ),
            )
        except (LookupError, tableau.RefreshMovedError) as exc:
            raise Refusal(f"cannot export {sheet!r}: {exc}") from exc
    return twb, columns, exportable, browser, captures[key]


def prove_headers(
    cfg: ViewConfig,
    path: Path,
    comparison_id: str,
    *,
    tbl: tableau.Tableau,
    captures: dict[tuple, tableau.Snapshot] | None = None,
) -> None:
    """Print each exported cut's column headers, and the fields a long export
    names, without probing or writing anything.
    """
    comparison = _comparison_by_id(cfg, path, comparison_id)
    _, _, exportable, _, snap = _capture(comparison, tbl, captures)
    for cut, rows in zip(exportable, snap.exports, strict=True):
        headers = list(rows[0]) if rows else []
        print(
            f"{comparison.id} cut {cut_label(cut)}: {', '.join(headers) or 'no rows'}"
        )
        if MEASURE_NAMES in headers:
            names = sorted({r[MEASURE_NAMES] for r in rows})
            print(f"  {MEASURE_NAMES}: {', '.join(names)}")


def prove(
    cfg: ViewConfig,
    path: Path,
    comparison_id: str,
    *,
    wh: Warehouse,
    tbl: tableau.Tableau,
    now: datetime,
    max_usd: float,
    captures: dict[tuple, tableau.Snapshot] | None = None,
    failures_dir: Path | None = None,
) -> tableau.Proof:
    """Prove a comparison's probe against the sheet and write `proof:`.

    Failures and browser cuts print to the terminal only: a count per reason
    and a few samples, with the full list in `failures_dir` when given.
    `captures` keeps each sheet's export across calls, so comparisons on one
    sheet and cuts share a capture.

    Raises:
        Refusal: The comparison is unknown or incomplete, an exportable cut
            has no rows on a side, or the proof failed.
    """
    comparison = _comparison_by_id(cfg, path, comparison_id)
    _require(comparison, "workbook", "sheet", "dashboard_view", "decimals")
    twb, columns, exportable, browser, snap = _capture(comparison, tbl, captures)
    if snap.refresh_started < now - PROOF_WINDOW:
        raise Refusal(
            f"the extract refreshed at {snap.refresh_started}, outside the 7 days "
            "of warehouse history; prove after the next refresh"
        )

    exports: list[dict] = []
    probes: list[dict] = []
    totals_skipped = 0
    with wh.budget(max_usd):
        for cut, rows in zip(exportable, snap.exports, strict=True):
            label = cut_label(cut)
            probe_rows = wh.rows(
                _as_of(probe_sql(cfg, comparison, cut), snap.refresh_started, wh).sql
            )
            if not rows or not probe_rows:
                side = "export" if not rows else "probe"
                raise Refusal(f"cut {label}: the {side} has no rows")
            rows = long_to_wide(rows, comparison.sheet_field)
            mapping, value = _export_columns(comparison, list(rows[0]), columns)
            cells, totals, summed = _export_cells(
                comparison, rows, mapping, value, columns, probe_rows
            )
            if totals:
                print(f"cut {label}: skipped {totals} total rows ({TOTAL_LABEL})")
            if summed:
                print(f"cut {label}: summed {summed} split export rows into others")
            totals_skipped += totals
            exports += [{**c, "cut": label} for c in cells]
            probes += [
                {
                    **{d.dashboard: r[d.dashboard] for d in comparison.dims},
                    "value": r["value"],
                    "cut": label,
                }
                for r in probe_rows
            ]

    try:
        proof = tableau.prove(comparison, exports, probes, twb_xml=twb, now=now)
    except ValueError as exc:
        raise Refusal(f"comparison {comparison.id!r}: {exc}") from exc
    for cut in browser:
        print(f"Prove in the browser: {cut_label(cut)}")
    if not proof.proven:
        print(f"Proof failed for {comparison.id} ({proof.cells} cells matched):")
        _print_failures(comparison.id, proof.failures, failures_dir)
        raise Refusal(f"comparison {comparison.id!r} is not proven; nothing written")

    gaps = sheet_gaps(twb, comparison)
    for kind, names in (("cuts", gaps.cuts), ("filters", gaps.filters)):
        if names:
            print(f"Sheet {kind} with no Cube member: {', '.join(names)}")

    write_proof(
        path,
        comparison.id,
        {
            "fingerprint": proof.fingerprint,
            "cells": proof.cells,
            "proven_at": proof.proven_at.isoformat(),
            "workbook_updated_at": tbl.workbook_updated(
                comparison.workbook or ""
            ).isoformat(),
            "probe_fingerprint": probe_fingerprint(cfg, comparison),
            # `run` lists every other cut as one to prove in the browser.
            "cuts": [cut_label(cut) for cut in exportable],
            # `run` lists these rows as totals no proof covered.
            "totals_skipped": totals_skipped,
            # `run` lists these as missing cuts and filters to triage.
            "missing_cuts": gaps.cuts,
            "missing_filters": gaps.filters,
            "restricting_filters": gaps.restricting,
        },
    )
    print(f"Proved {comparison.id}: {proof.cells} cells; wrote proof to {path}.")
    return proof


FAILURE_SAMPLES = 5


def _failure_reason(failure: str) -> str:
    if " decimals (" in failure:
        return "value differs at the displayed decimals"
    return failure.rsplit(": ", 1)[-1]


def _print_failures(
    comparison_id: str, failures: list[str], failures_dir: Path | None
) -> None:
    """Print a count per reason and a few samples; save the full list locally.

    A failure line can name a student, so the full list stays in the local
    cache, never in anything posted.
    """
    for reason, n in Counter(map(_failure_reason, failures)).most_common():
        print(f"  {n} x {reason}")
    print(f"  First {min(FAILURE_SAMPLES, len(failures))} of {len(failures)}:")
    for failure in failures[:FAILURE_SAMPLES]:
        print(f"    {failure}")
    if failures_dir is not None:
        failures_dir.mkdir(parents=True, exist_ok=True)
        path = failures_dir / f"prove-failures-{comparison_id}.txt"
        path.write_text("\n".join(failures) + "\n")
        print(f"  Full list: {path}")


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
    caption: str | None = None,
    limit: int | None = finder.TOP_N,
) -> list[finder.Candidate]:
    """Print workbook fields ranked against a measure, then each listed sheet's
    shape: shelves, export form, displayed decimals and filters.

    Calculated fields and aggregated raw fields both rank; a formula that uses a
    code group shows its codes. `caption` boosts the dashboard's name for the
    measure; `limit` None prints every candidate.
    """
    compiled = cube.compiled({"measures": [_member(cfg.view, measure)]})
    member_sql = _measure_expression(compiled.sql, cfg.view, measure)

    exposures = finder.tableau_exposures(exposures_path)
    if exposures.skipped:
        print(
            f"Skipped exposures without a luid or models: {', '.join(exposures.skipped)}"
        )

    found: list[finder.Candidate] = []
    twbs: dict[str, str] = {}
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
        twbs[exposure.luid] = twb
        found += finder.rank(
            measure,
            member_sql,
            finder.calculated_fields(twb) + finder.aggregated_fields(twb),
            workbook_luid=exposure.luid,
            workbook_label=exposure.label,
            caption=caption,
            limit=None,
        )

    found.sort(key=lambda c: (-c.score, c.workbook_label, c.caption))
    found = found if limit is None else found[:limit]
    if not found:
        print(f"No candidates for {measure}.")
    for c in found:
        formula = finder.explain_bins(
            " ".join(c.formula.split()), finder.bins(twbs[c.workbook_luid])
        )
        print(
            f"{c.score:.2f}  {c.workbook_label} ({c.workbook_luid})  "
            f"{c.caption!r} on {', '.join(c.worksheets) or 'no sheet'}: {formula}"
        )
    _print_sheets(found, twbs)
    return found


def _print_sheets(found: list[finder.Candidate], twbs: dict[str, str]) -> None:
    sheets = list(
        dict.fromkeys(
            (c.workbook_luid, c.workbook_label, s) for c in found for s in c.worksheets
        )
    )
    if not sheets:
        return
    print("\nSheets:")
    for luid, label, sheet in sheets:
        shape = finder.sheet_shape(twbs[luid], sheet)
        print(
            f"  {sheet} ({label}): rows {', '.join(shape.rows) or 'none'}; "
            f"columns {', '.join(shape.cols) or 'none'}"
        )
        export = (
            "long (set sheet_field to a Measure Names value)"
            if shape.long_export
            else "wide"
        )
        print(f"    export: {export}")
        if shape.decimals:
            shown = ", ".join(f"{k} {v}" for k, v in shape.decimals.items())
            print(f"    decimals: {shown}")
        for line in shape.filters:
            print(f"    filter {line}")


def utc(value: str) -> datetime:
    """Parse an ISO moment; naive input is refused, aware input kept."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{value!r} has no time zone; add Z or an offset")
    return parsed.astimezone(timezone.utc)
