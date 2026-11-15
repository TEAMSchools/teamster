"""What each command does, wired from the other modules.

`cli.py` parses arguments and builds the clients; the functions here take those
clients as arguments so tests can pass fakes. The dashboard side is read as of
a fact build's start and Cube as of its end. Every BigQuery query runs inside
`Warehouse.budget`, and only aggregates come back: row-level comparisons run
inside BigQuery through `reconcile.reconcile_sql`.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import json
import re
import subprocess
import sys
import uuid

# trunk-ignore(bandit/B405): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import tableauserverclient as TSC
from google.api_core.exceptions import GoogleAPIError

from . import answers, checkpoints, coverage, decisions
from . import find_field as finder
from . import latest, reconcile, report, saved, sort, tableau
from .bq import CostCapError, ViewHistoryError, Warehouse, job_failure
from .config import (
    WEEK_END_KEY,
    ColumnPair,
    Comparison,
    Decision,
    ViewConfig,
    write_rebuild_check,
)
from .cube_client import (
    Compiled,
    Cube,
    CubeError,
    CubeRefusal,
    bind,
    drop_limit,
    network_schools,
    refuse_unless_safe,
    sort_school_filters,
)
from .decisions import Applied
from .moment import (
    WINDOW,
    Build,
    MomentError,
    changed_between,
    fact_builds,
    fingerprint_sql,
    pick_moment,
)
from .reconcile import CellDiff, Gap, Group
from .report import MeasureResult, RunResult
from .timetravel import PROJECT, AsOf, as_of, repin, utc_literal

# A rebuild's sheet query is time-travelled to the refresh; keep a margin inside
# 7 days.
REBUILD_WINDOW = WINDOW - timedelta(hours=1)


class Refusal(RuntimeError):
    """A command stopped on purpose; the message says why."""


@dataclasses.dataclass(frozen=True)
class Skip:
    """A comparison `compare` leaves out, and why; it keeps its latest result."""

    comparison: str
    why: str


def _skip_keys(skips: Iterable[Skip]) -> list[tuple[str, str]]:
    """Each skip as its comparison and the stable head of its reason.

    The head is the text before the first `:` or `(`, past which a reason
    carries what varies between runs (an error's message, a job id, a
    build's times), so the same skip twice keys alike.
    """
    return [
        (s.comparison, re.split(r"[:(]", s.why, maxsplit=1)[0].strip()) for s in skips
    ]


def _say_skips(skips: list[Skip]) -> None:
    for s in skips:
        print(f"Skipping {s.comparison}: {s.why}.")


def _refuse_all_skipped(
    cfg: ViewConfig, comparisons: list[Comparison], skips: list[Skip]
) -> None:
    """Refuse when every one of `comparisons` is skipped: nothing would run.

    Raises:
        Refusal: Every comparison is in `skips`.
    """
    if {c.id for c in comparisons} <= {s.comparison for s in skips}:
        raise Refusal(
            f"{cfg.view}: every comparison was skipped; see the reasons above"
        )


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
        for f in reconcile.scope_filters(comparison)
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


# The coming Sunday in New York, as Tableau's `TODAY() + 8 - weekday` (Sunday is
# 1 in both). `pin_clock` pins CURRENT_DATE to the run's moment. This assumes
# Tableau Server's TODAY() is Eastern; if its clock is not, the two disagree on
# the week from 8 pm ET Saturday to midnight, so the runbook says not to start a
# run then.
_TODAY = "CURRENT_DATE('America/New_York')"
_WEEK_END = f"8 - EXTRACT(DAYOFWEEK FROM {_TODAY})"


def _week_end_sql(days: int) -> str:
    """The coming Sunday plus `days`, as a BigQuery date."""
    offset = f" {'+' if days > 0 else '-'} {abs(days)}" if days else ""
    return f"DATE_ADD({_TODAY}, INTERVAL {_WEEK_END}{offset} DAY)"


def _dashboard_filter_sql(entry: dict[str, Any]) -> str:
    """One `dashboard_filters` entry as SQL; `not_equals` keeps nulls, as Cube's does."""
    column, operator = entry["dashboard"], entry["operator"]
    if operator == "set":
        return f"{column} IS NOT NULL"
    if (days := entry.get(WEEK_END_KEY)) is not None:
        return f"{column} {_SQL_COMPARE[operator]} {_week_end_sql(days)}"
    if operator in _SQL_COMPARE:
        return f"{column} {_SQL_COMPARE[operator]} {_lit(entry['values'][0])}"
    match = _column_predicate(column, entry["values"])
    return match if operator == "equals" else f"({column} IS NULL OR NOT {match})"


def dashboard_predicate(
    comparison: Comparison, cut: dict[str, Any], with_filters: bool = True
) -> str:
    """Return the WHERE predicate a cut puts on the dashboard rows.

    It ends with the comparison's `dashboard_filters`, which Cube never sees,
    unless `with_filters` is False.
    """
    parts = [
        _column_predicate(comparison.filters[caption].dashboard, value)
        for caption, value in effective_filters(comparison, cut).items()
    ]
    if with_filters:
        parts += [_dashboard_filter_sql(e) for e in comparison.dashboard_filters]
    return " AND ".join(parts) or "TRUE"


def _any_cut_predicate(comparison: Comparison, with_filters: bool = True) -> str:
    """OR of every cut, so a row-level reconcile counts each row once."""
    preds = [
        dashboard_predicate(comparison, cut, with_filters) for cut in _cuts(comparison)
    ]
    if "TRUE" in preds:
        return "TRUE"
    return preds[0] if len(preds) == 1 else " OR ".join(f"({p})" for p in preds)


def _varying_captions(comparison: Comparison) -> list[str]:
    """The captions whose value differs across the comparison's cuts.

    A caption with one value in every cut (a default no cut changes) cannot
    split the cells.
    """
    chosen = [effective_filters(comparison, cut) for cut in _cuts(comparison)]
    captions = dict.fromkeys(c for f in chosen for c in f)
    return [
        c
        for c in captions
        if len({json.dumps(f.get(c), sort_keys=True, default=str) for f in chosen}) > 1
    ]


def cut_flags(comparison: Comparison) -> list[tuple[str, str, str]] | None:
    """Per cut, its label and the predicates that keep its rows on each side
    of the row reconcile (over `c.` and `d.` row columns), or None without
    `rows`.

    Only the captions that vary across cuts (`_varying_captions`) split the
    cells; `_row_pairs` makes each of them a row column on both sides.
    """
    cuts = _cuts(comparison)
    if comparison.rows is None:
        return None
    chosen = [effective_filters(comparison, cut) for cut in cuts]
    varying = _varying_captions(comparison)
    out = []
    for cut, f in zip(cuts, chosen, strict=True):
        sides = []
        for side in ("cube", "dashboard"):
            prefix = "c" if side == "cube" else "d"
            parts = [
                _column_predicate(
                    f"{prefix}.{getattr(comparison.filters[c], side)}", f[c]
                )
                for c in varying
                if c in f
            ]
            sides.append(" AND ".join(parts) or "TRUE")
        out.append((cut_label(cut), sides[0], sides[1]))
    return out


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
    """The columns a comparison's row SQL selects on each side.

    With `rows`: the grain, the values, the dims, and each caption that varies
    across cuts, so the reconcile can tell the cuts' rows apart (`cut_flags`).
    """
    rows = comparison.rows
    if rows is None:
        return list(comparison.dims)
    pairs = [*rows.grain, *rows.values, *comparison.dims]
    for caption in _varying_captions(comparison):
        pair = comparison.filters[caption]
        if pair not in pairs:
            pairs.append(pair)
    return pairs


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
    table = f"`{PROJECT}`.`{ds}`.`{name}`"
    if not comparison.dashboard_columns:
        return table
    computed = ", ".join(
        f"{sql} AS {column}" for column, sql in comparison.dashboard_columns.items()
    )
    # trunk-ignore(bandit/B608): column names are validated in config.py; the expressions are the analyst's own SQL, like sheet_query_sql
    return f"(SELECT *, {computed} FROM {table})"


def _date_cubes(cfg: ViewConfig) -> set[str]:
    return {cfg.time_dimension} if cfg.time_dimension else set()


def _select(name: str, source: str, is_date: bool) -> str:
    return f"DATE({source}) AS {name}" if is_date else f"{source} AS {name}"


def dashboard_rows_sql(cfg: ViewConfig, comparison: Comparison) -> str:
    """Return the dashboard's rows for the row-level reconcile, every cut.

    Rows a `dashboard_filters` entry drops stay in, with a flag per entry
    (`__df0`, ...) that says whether it keeps the row, so the reconcile can
    count them apart from rows Cube alone has. Rows outside `rows.dashboard_scope`
    are left out.

    With `rows.reduce`, the rows above are cut to the latest per grain key
    within each cut (the captions that vary across cuts join the key). The
    cuts, `dashboard_scope` and `dashboard_filters` decide first which rows
    compete: a row every filter keeps outranks one a filter drops, so a key
    whose latest day a filter drops reads its latest kept day. A tie on the
    latest value keeps every tied row, for the reconcile to report as
    duplicates.
    """
    dates = _date_cubes(cfg)
    seen: dict[str, bool] = {}
    for p in _row_pairs(comparison):
        seen.setdefault(p.dashboard, p.cube in dates)
    cols = [
        f"DATE({name}) AS {name}" if is_date else name for name, is_date in seen.items()
    ] + [
        f"COALESCE({_dashboard_filter_sql(e)}, FALSE) AS {flag}"
        for e, (flag, _) in zip(
            comparison.dashboard_filters, _filter_flags(comparison), strict=True
        )
    ]
    where = _any_cut_predicate(comparison, with_filters=False)
    if scope := comparison.rows.dashboard_scope if comparison.rows else []:
        parts = [where, *map(_dashboard_filter_sql, scope)]
        where = " AND ".join(f"({p})" for p in parts)
    reduce = comparison.rows.reduce if comparison.rows else {}
    if reduce:
        cols.append(f"{reduce['by']} AS __reduce_by")
    # trunk-ignore(bandit/B608): identifiers are validated in config.py and values are bound or literal-escaped
    sql = f"SELECT {', '.join(cols)} FROM {_dashboard_ref(comparison)} WHERE {where}"
    if not reduce:
        return sql
    split = [comparison.filters[c].dashboard for c in _varying_captions(comparison)]
    keys = ", ".join(_unique([p.dashboard for p in comparison.rows.grain] + split))
    kept = [f"{flag} AND " for flag, _ in _filter_flags(comparison)]
    order = (
        f"({''.join(kept)}TRUE) DESC, __reduce_by DESC" if kept else "__reduce_by DESC"
    )
    return (
        # trunk-ignore(bandit/B608): identifiers are validated in config.py
        f"SELECT * EXCEPT (__reduce_by) FROM ({sql}) "
        f"QUALIFY RANK() OVER (PARTITION BY {keys} ORDER BY {order}) = 1"
    )


def _students_sql(cfg: ViewConfig, comparison: Comparison, student: str) -> str:
    """Return distinct `student` values per cell, one `UNION ALL` branch per cut.

    Each branch reads exactly the rows its cut's cells come from: the cut's
    predicate with the `dashboard_filters`, grouped by the dims as
    `sheet_query_sql` groups them. `__cut` is the cut's index in `_cuts`.
    """
    # trunk-ignore(bandit/B608): identifiers are validated in config.py and values are bound or literal-escaped
    rows = f"SELECT * FROM {_dashboard_ref(comparison)}"
    dates = _date_cubes(cfg)
    dims = [
        f"DATE({d.dashboard}) AS {d.dashboard}" if d.cube in dates else d.dashboard
        for d in comparison.dims
    ]
    group = (
        " GROUP BY " + ", ".join(str(i + 2) for i in range(len(dims))) if dims else ""
    )
    count = f"COUNT(DISTINCT {student}) AS n_students"
    return " UNION ALL ".join(
        # trunk-ignore(bandit/B608): identifiers are validated in config.py and values are bound or literal-escaped
        f"(SELECT {', '.join([f'{i} AS __cut', *dims, count])} FROM ({rows}) "
        f"WHERE {dashboard_predicate(comparison, cut)}{group})"
        for i, cut in enumerate(_cuts(comparison))
    )


def _filter_flags(comparison: Comparison) -> list[tuple[str, str]]:
    """Each dashboard-only filter's flag column and label (its column)."""
    return [
        (f"__df{i}", e["dashboard"]) for i, e in enumerate(comparison.dashboard_filters)
    ]


def group_dims(comparison: Comparison) -> list[ColumnPair]:
    """The dims a row group splits by: never one that is part of the row grain,
    so a group (and any decision on it) never carries a student's value.
    """
    grain = {p.cube for p in comparison.rows.grain} if comparison.rows else set()
    return [d for d in comparison.dims if d.cube not in grain]


def sheet_query(
    cfg: ViewConfig,
    comparison: Comparison,
    cut: dict[str, Any],
    with_filters: bool = True,
) -> str:
    """Return the sheet query over the dashboard rows under one cut, before time
    travel.

    `sheet_query` is an aggregate over the rows; `sheet_query_sql` is a template whose
    `{rows}`, `{where}` and `{dims}` are filled here. `with_filters` False
    leaves out the `dashboard_filters`, to name the cells they drop.
    """
    # trunk-ignore(bandit/B608): identifiers are validated in config.py and values are bound or literal-escaped
    rows = f"SELECT * FROM {_dashboard_ref(comparison)}"
    where = dashboard_predicate(comparison, cut, with_filters)
    names = [d.dashboard for d in comparison.dims]
    if comparison.sheet_query_sql:
        return comparison.sheet_query_sql.format(
            rows=rows, where=where, dims=", ".join(names)
        )
    if not comparison.sheet_query:
        raise Refusal(
            f"comparison {comparison.id!r} has no sheet_query or sheet_query_sql"
        )
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
        f"SELECT {', '.join([*select, f'{comparison.sheet_query} AS value'])} "
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
    """Cell key text: dates by day, booleans as `true`/`false`, numbers by
    value, else the text.

    Tableau's export writes a date as M/D/YYYY (the server's en-US format),
    the sheet query and Cube as ISO, so both read as the same day. A boolean
    reads as BigQuery casts it, whatever its case, so a group label
    (`reconcile._label`) keys as its cell does; `reconcile._cell_key` is
    this rule in SQL.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str) and re.match(r"\d{4}-\d{2}-\d{2}", value):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            pass
    elif isinstance(value, str) and (day := tableau.export_date(value)) is not None:
        value = day
    if isinstance(value, datetime):
        stamp = value.replace(tzinfo=None)
        return stamp.date().isoformat() if stamp.time() == time() else stamp.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in ("true", "false"):
        return text.lower()
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
    # The cell's dims by Cube name, for candidate causes; never printed whole.
    dims: tuple[tuple[str, str], ...] = ()


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
    unfiltered_rows: list[dict] | None = None,
) -> list[Cell]:
    """Compare a cut's cells. A Cube-only cell that the sheet query without the
    `dashboard_filters` reproduces reads `dashboard_filtered`: the sheet's
    dashboard-only filter drops it, so it is explained, not a difference.
    """
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
    unfiltered = (
        _by_key(
            unfiltered_rows,
            lambda r: tuple(_key(r[d.dashboard]) for d in comparison.dims),
            lambda r: _number(r["value"]),
            f"{where} dashboard without its dashboard-only filters",
        )
        if unfiltered_rows is not None
        else {}
    )
    cells = []
    for key in sorted(dash.keys() | cube.keys()):
        label = ", ".join(
            f"{d.cube}={v}" for d, v in zip(comparison.dims, key, strict=True)
        )
        verdict = reconcile.cell_verdict(dash.get(key), cube.get(key), decimals)
        if (
            verdict == "cube_only"
            and key in unfiltered
            and reconcile.cell_verdict(unfiltered[key], cube[key], decimals) == "pass"
        ):
            verdict = "dashboard_filtered"
        cells.append(
            Cell(
                comparison.id,
                cut_label(cut),
                label or "(total)",
                dash.get(key),
                cube.get(key),
                verdict,
                tuple((d.cube, v) for d, v in zip(comparison.dims, key, strict=True)),
            )
        )
    return cells


DIFFERING = ("differs", "cube_only", "dashboard_only")


def candidate_causes(
    comparison: Comparison, cells: list[Cell], decimals: int, cube_expr: str
) -> list[str]:
    """What the differing cells suggest, for the analyst to check, not a verdict.

    Patterns (blank against 0, 1 display unit apart), where the cells cluster
    (a cut, a dim value), and both definitions side by side. A dim that is part
    of the row grain never shows, so no student's value does.
    """
    n = len(cells)
    patterns: Counter = Counter()
    unit = Decimal(1).scaleb(-decimals)
    for c in cells:
        if c.cube is None:
            patterns[
                "Cube is blank where the dashboard shows 0"
                if c.dashboard == 0
                else "Cube is blank where the dashboard shows a value"
            ] += 1
        elif c.dashboard is None:
            patterns[
                "Cube shows 0 where the dashboard is blank"
                if c.cube == 0
                else "Cube shows a value where the dashboard is blank"
            ] += 1
        elif (
            abs(
                reconcile._half_up(c.dashboard, decimals)
                - reconcile._half_up(c.cube, decimals)
            )
            == unit
        ):
            patterns[f"1 display unit apart at {decimals} decimals"] += 1
        else:
            patterns["values differ beyond rounding"] += 1
    out = [
        f"{k} {'cell' if k == 1 else 'cells'}: {pattern}"
        for pattern, k in patterns.most_common()
    ]
    cuts = Counter(c.cut for c in cells)
    top_cut, k = cuts.most_common(1)[0]
    if 2 * k >= n and (len(cuts) > 1 or top_cut != cut_label({})):
        out.append(f"{k} of {n} in cut {top_cut}")
    for dim in group_dims(comparison):
        values = Counter(dict(c.dims).get(dim.cube) for c in cells)
        value, k = values.most_common(1)[0]
        if value is not None and 2 * k >= n:
            out.append(f"{k} of {n} have {dim.cube} = {value}")
    query = comparison.sheet_query or " ".join(
        (comparison.sheet_query_sql or "").split()
    )
    out.append(
        f"Cube computes `{comparison.measure}` as {cube_expr}; the sheet query is "
        f"{query}"
    )
    if comparison.definitions:
        out.append(
            f"Recorded definitions: dashboard {comparison.definitions['dashboard']}; "
            f"Cube {comparison.definitions['cube']}"
        )
    return out


def row_group_cause(n_groups: int) -> str:
    """The cause line a row-level comparison adds: its row groups, or none."""
    return (
        f"{n_groups} row groups on this comparison (see Sort) may explain part of it"
        if n_groups
        else "every row matches on the grain and values, so the 2 definitions or "
        "their filters differ"
    )


def _cell_diffs(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    sides: "_Sides",
    cube: Cube,
    older: frozenset[str] = frozenset(),
) -> tuple[list[CellDiff], set[Cell]]:
    """Each comparison's differing cells, with candidate causes.

    A cell `coverage.placed` finds no group in is a formula difference: every
    row in it matched on both sides. Those cells make the comparison's
    `formula` diff; the rest, holding groups or unplaceable, its `cells` diff.
    A cell that cannot be placed is never a formula difference. A comparison
    in `older` (not compared by this process) composes its older cells even
    when Cube can no longer compile its measure.

    Returns:
        The diffs, and the formula cells, which `_diff_cells` marks so later
        steps read this split instead of placing the cells again.
    """
    out = []
    formula_cells: set[Cell] = set()
    for comparison in comparisons:
        differing = [
            c for c in sides.cells
            if c.comparison == comparison.id and c.verdict in DIFFERING
        ]  # fmt: skip
        if not differing:
            continue
        member = _member(cfg.view, comparison.measure)
        try:
            compiled = cube.compiled({"measures": [member]}).sql
        except CubeError:
            if comparison.id not in older:
                raise
            expr = "a measure Cube cannot compile today"
        else:
            expr = _measure_expression(compiled, cfg.view, comparison.measure)
        formula: list[Cell] = []
        cells: list[Cell] = []
        for c in differing:
            inside = coverage.placed(_coverage_cell(c), sides.groups, comparison)
            (formula if inside == [] else cells).append(c)
        formula_cells.update(formula)
        if cells:
            causes = candidate_causes(comparison, cells, comparison.decimals or 0, expr)
            if comparison.rows is not None:
                groups = [g for g in sides.groups if g.comparison_id == comparison.id]
                causes.append(row_group_cause(len(groups)))
            out.append(
                CellDiff(
                    comparison.id,
                    dict(Counter(c.verdict for c in cells)),
                    tuple(causes),
                )
            )
        if formula:
            causes = [
                f"{len(formula)} differing cells hold no unmatched row",
                *candidate_causes(comparison, formula, comparison.decimals or 0, expr),
            ]
            out.append(
                CellDiff(
                    comparison.id,
                    dict(Counter(c.verdict for c in formula)),
                    tuple(causes),
                    kind="formula",
                )
            )
    return out, formula_cells


def _coverage_cell(c: Cell) -> dict:
    """A cell as `coverage` reads it, the shape `run.json` saves it in."""
    return {"cut": c.cut, "dims": [list(d) for d in c.dims]}


# --- compare -----------------------------------------------------------------


def _require(comparison: Comparison, *keys: str) -> None:
    missing = [k for k in keys if getattr(comparison, k) in (None, "")]
    if missing:
        raise Refusal(f"comparison {comparison.id!r} has no {', '.join(missing)}")


def sheet_query_fingerprint(cfg: ViewConfig, comparison: Comparison) -> str:
    """Fingerprint the sheet query a rebuild check covers: the default cut's SQL.

    It covers the sheet query text, dims, defaults and dashboard view; `compare`
    refuses a rebuild check whose sheet query has changed since.
    """
    base = decisions.sql_fingerprint(sheet_query(cfg, comparison, {}))
    # How the export is read is part of what a rebuild check covers. Unset keys
    # add nothing, so a check written before them keeps its fingerprint.
    extras = [f"sheet_field={comparison.sheet_field}"] if comparison.sheet_field else []
    if comparison.split_rows != "refuse":
        extras.append(f"split_rows={comparison.split_rows}")
    if comparison.parameters:
        extras.append(f"parameters={json.dumps(comparison.parameters, sort_keys=True)}")
    if comparison.shelves:
        extras.append(f"shelves={json.dumps(comparison.shelves, sort_keys=True)}")
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
    """What a run collects across comparisons, or one comparison's slice of it.

    Each comparison returns its own slice (`_execute`); `compare` merges them
    in config order and keeps each as a checkpoint (`to_json`).
    """

    cube_tables: set[str] = dataclasses.field(default_factory=set)
    live: set[str] = dataclasses.field(default_factory=set)
    cells: list[Cell] = dataclasses.field(default_factory=list)
    groups: list[Group] = dataclasses.field(default_factory=list)
    sql: dict[str, tuple[str, str]] = dataclasses.field(default_factory=dict)
    fingerprints: dict[str, dict[str, str]] = dataclasses.field(default_factory=dict)
    moved: dict[str, bool] = dataclasses.field(default_factory=dict)
    # Per comparison and cut label, the [dashboard, Cube] SQL run and its price.
    cell_sql: dict[str, dict[str, list[str]]] = dataclasses.field(default_factory=dict)
    cell_sql_usd: dict[str, dict[str, list[float]]] = dataclasses.field(
        default_factory=dict
    )
    # Per comparison with `rows`, distinct students by (cut label, cell key).
    students: dict[str, dict[tuple[str, tuple[str, ...]], int]] = dataclasses.field(
        default_factory=dict
    )

    def merge(self, other: _Sides) -> None:
        """Add another slice: its sets, cells, groups and every per-comparison
        entry."""
        self.cube_tables |= other.cube_tables
        self.live |= other.live
        self.moved |= other.moved
        self.cells += other.cells
        self.groups += other.groups
        for name in (
            "sql",
            "fingerprints",
            "cell_sql",
            "cell_sql_usd",
            "students",
        ):
            getattr(self, name).update(getattr(other, name))

    def to_json(self) -> dict:
        """The slice as JSON data: counts, SQL and fingerprints, no student
        row."""
        return {
            "cube_tables": sorted(self.cube_tables),
            "live": sorted(self.live),
            "cells": [dataclasses.asdict(c) for c in self.cells],
            "groups": [dataclasses.asdict(g) for g in self.groups],
            "sql": {k: list(v) for k, v in self.sql.items()},
            "fingerprints": self.fingerprints,
            "moved": self.moved,
            "cell_sql": self.cell_sql,
            "cell_sql_usd": self.cell_sql_usd,
            "students": {
                cid: [[cut, list(key), n] for (cut, key), n in by.items()]
                for cid, by in self.students.items()
            },
        }

    @classmethod
    def from_json(cls, data: dict) -> _Sides:
        """The slice `to_json` wrote, with its tuples restored."""

        def pairs(dims) -> tuple:
            return tuple(tuple(p) for p in dims)

        return cls(
            cube_tables=set(data["cube_tables"]),
            live=set(data["live"]),
            cells=[Cell(**{**c, "dims": pairs(c["dims"])}) for c in data["cells"]],
            groups=[_group(g) for g in data["groups"]],
            sql={k: (v[0], v[1]) for k, v in data["sql"].items()},
            fingerprints=data["fingerprints"],
            moved=data["moved"],
            cell_sql=data["cell_sql"],
            cell_sql_usd=data["cell_sql_usd"],
            students={
                cid: {(cut, tuple(key)): n for cut, key, n in entries}
                for cid, entries in data["students"].items()
            },
        )


class _Expand:
    """Compile Cube queries and expand SQL as of a moment, each once.

    One per comparison: the cells, the rows and the fingerprints read the same
    compiled and expanded SQL.
    """

    def __init__(
        self, cfg: ViewConfig, cube: Cube, schools: set[str], wh: Warehouse
    ) -> None:
        self._cfg, self._cube, self._schools, self._wh = cfg, cube, schools, wh
        self._compiled: dict[tuple[str, bool], str] = {}
        self._expanded: dict[tuple[str, datetime], AsOf] = {}

    def cube_sql(self, query: dict, rows: bool = False) -> str:
        key = (json.dumps(query, sort_keys=True), rows)
        if key not in self._compiled:
            self._compiled[key] = _cube_sql(
                self._cfg, self._cube, query, self._schools, rows=rows
            )
        return self._compiled[key]

    def at(self, sql: str, ts: datetime) -> AsOf:
        if (sql, ts) not in self._expanded:
            self._expanded[(sql, ts)] = _as_of(sql, ts, self._wh)
        return self._expanded[(sql, ts)]


def _fingerprints(
    cfg: ViewConfig, comparison: Comparison, ex: _Expand, build: Build
) -> dict[str, str]:
    """Both sides' SQL fingerprints: each side's cell and row SQL, expanded
    through every view as of the moment and with the moment masked, so a view
    or member edit changes them and a new moment does not."""
    cube_parts = [
        _masked(
            ex.at(ex.cube_sql(cell_query(cfg.view, comparison, {})), build.end),
            build.end,
        )
    ]
    dash_parts = [
        _masked(ex.at(sheet_query(cfg, comparison, {}), build.start), build.start)
    ]
    if comparison.rows is not None:
        cube_parts.append(
            _masked(
                ex.at(
                    ex.cube_sql(row_query(cfg.view, comparison), rows=True), build.end
                ),
                build.end,
            )
        )
        dash_parts.append(
            _masked(
                ex.at(dashboard_rows_sql(cfg, comparison), build.start), build.start
            )
        )
    return {
        "cube": decisions.sql_fingerprint(sort_school_filters("\n".join(cube_parts))),
        "dashboard": decisions.sql_fingerprint("\n".join(dash_parts)),
    }


def side_fingerprints(
    cfg: ViewConfig,
    comparison: Comparison,
    *,
    wh: Warehouse,
    cube: Cube,
    build: Build,
    schools: set[str],
) -> dict[str, str]:
    """The `cube` and `dashboard` fingerprints `compare` records for a comparison,
    from compiled and expanded SQL only: no query runs."""
    return _fingerprints(cfg, comparison, _Expand(cfg, cube, schools, wh), build)


def checkpoint_fingerprint(comparison: Comparison, fingerprints: dict[str, str]) -> str:
    """What a comparison's saved work holds for: its config entry and both
    sides' SQL. Any edit to either makes the saved work stale, but its
    `definitions`, which change no result."""
    return hashlib.sha256(
        json.dumps(
            [
                dataclasses.asdict(dataclasses.replace(comparison, definitions={})),
                fingerprints,
            ],
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()


NEVER_COMPARED = "never compared"
ENTRY_CHANGED = "its entry or rebuild check changed"
SQL_BROKEN = report.SQL_BROKEN


def composed_results(cfg: ViewConfig, run: RunResult) -> dict[str, latest.Latest]:
    """The results `compare` was composed from, as `stale_comparisons` reads them.

    Built from the run itself, not from `latest/`: a run stopped after
    keeping a newer result, before composing, still holds the older one.
    A comparison the run lacks is left out, so it reads as never compared.
    """
    return {
        c.id: latest.Latest(
            moment=run.moment_of(c.id),
            # The entry is checked first, so today's entry stands in for the
            # one the run compared whenever this fingerprint is read.
            fingerprint=checkpoint_fingerprint(c, run.fingerprints[c.id]),
            entry=run.entries.get(c.id, ""),
            ran_at="",
            data={"fingerprints": {c.id: run.fingerprints[c.id]}},
            fact=run.fact,
        )
        for c in cfg.comparisons
        if c.id in run.fingerprints and c.id not in run.missing
    }


def stale_comparisons(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    results: dict[str, latest.Latest],
    *,
    wh: Warehouse,
    cube: Cube,
    schools: set[str],
    now: datetime,
) -> dict[str, str]:
    """Each confirmed comparison whose latest result is missing or stale, and why.

    A result is stale when its `checkpoint_fingerprint` differs from today's:
    its entry or rebuild check changed, or either side's SQL did (Cube's
    compiled query, or the dashboard's sheet query and the views it reads).
    The fingerprints mask the moment, so a new build alone, or changed data,
    is not stale. A comparison whose SQL cannot be built today, a member Cube
    no longer compiles included, is named with why, and the others are still
    checked. Compiles and expands only; no query bills.
    """
    build = Build(now, now, "now")
    out: dict[str, str] = {}
    for c in comparisons:
        if not c.confirmed:
            continue
        held = results.get(c.id)
        if held is None:
            out[c.id] = NEVER_COMPARED
            continue
        if latest.entry_fingerprint(c) != held.entry:
            out[c.id] = ENTRY_CHANGED
            continue
        try:
            today = side_fingerprints(
                cfg, c, wh=wh, cube=cube, build=build, schools=schools
            )
        except _SQL_ERRORS as exc:
            out[c.id] = _sql_broken(exc)
            continue
        if checkpoint_fingerprint(c, today) == held.fingerprint:
            continue
        was = held.data.get("fingerprints", {}).get(c.id, {})
        why = [
            text
            for side, text in (
                ("cube", "Cube's SQL changed"),
                ("dashboard", "the dashboard SQL changed"),
            )
            if was.get(side) != today[side]
        ]
        out[c.id] = " and ".join(why) or ENTRY_CHANGED
    return out


def _reconcile_args(
    cfg: ViewConfig, comparison: Comparison, sides: RowSides
) -> tuple[tuple, dict]:
    """The positional and keyword arguments every row query of a comparison
    takes (`reconcile.reconcile_script`, `unmatched_rows_sql`)."""
    flags = cut_flags(comparison) or []
    args = (
        wrap_cube(sides.cube_rows_sql, cfg.view, sides.columns, _date_cubes(cfg), None),
        sides.dashboard.sql,
        comparison.rows,
        group_dims(comparison),
    )
    return args, {
        "filters": _filter_flags(comparison),
        "cuts": [(c, d) for _, c, d in flags],
    }


def save_script(
    cfg: ViewConfig,
    comparison: Comparison,
    sides: RowSides,
    table: str,
    labels: dict[str, str] | None,
) -> list[str]:
    """The reconcile that also saves the comparison's unmatched rows to `table`.

    With `labels`, the table carries them and expires after
    `saved.SAVED_DAYS`; without (an offline test on DuckDB), it is a plain
    table.
    """
    args, kwargs = _reconcile_args(cfg, comparison, sides)
    return reconcile.reconcile_script(
        *args,
        **kwargs,
        table=table,
        labels=labels,
        expire_days=saved.SAVED_DAYS if labels is not None else None,
    )


def inline_unmatched(cfg: ViewConfig, comparison: Comparison, sides: RowSides) -> str:
    """The rows `save_script` saves, as one query with no table, for a dry run."""
    args, kwargs = _reconcile_args(cfg, comparison, sides)
    return reconcile.unmatched_rows_sql(*args, **kwargs)


def _cube_sql(
    cfg: ViewConfig,
    cube: Cube,
    query: dict,
    schools: set[str],
    *,
    rows: bool = False,
) -> str:
    compiled = cube.compiled(query)
    refuse_unless_safe(
        compiled,
        view_fact=cfg.fact,
        network_schools=schools,
        also_facts=cfg.also_facts,
    )
    bound = bind(compiled)
    return drop_limit(bound) if rows else bound


@dataclasses.dataclass(frozen=True)
class _CutPlan:
    """One cut's cell queries: the dashboard's, Cube's wrapped one, and the
    dashboard's again without its `dashboard_filters` when it has any."""

    label: str
    dash_sql: str
    cube_sql: str
    unfiltered_sql: str | None


@dataclasses.dataclass
class _Plan:
    """Everything comparing one comparison will run, built before any of it
    bills (`_plan_one`), so `compare` can price the whole run first.

    `shared` lists the tables both sides' rows read. `moved` holds whether
    each changed during the build; it is empty until `_compare_all` has
    fingerprinted them, after the price.
    """

    comparison: Comparison
    fingerprints: dict[str, str]
    cuts: list[_CutPlan]
    rows: RowSides | None
    # The save script's rows as 1 query (`inline_unmatched`), to price it.
    unmatched_sql: str | None
    shared: list[str]
    students_sql: str | None
    cube_tables: set[str]
    live: set[str]
    moved: dict[str, bool] = dataclasses.field(default_factory=dict)

    def queries(self) -> list[str]:
        """Every query that bills, in the order `_execute` reads their prices:
        each cut's dashboard, Cube and unfiltered queries, the unmatched rows,
        the student count.

        The save script's temp table cannot be dry-run before it exists, so
        its join (`inline_unmatched`) stands in for it; the script's reads of
        that table still run under `Warehouse.rows`' billing cap.
        """
        out: list[str] = []
        for cut in self.cuts:
            out += [cut.dash_sql, cut.cube_sql]
            if cut.unfiltered_sql is not None:
                out.append(cut.unfiltered_sql)
        if self.unmatched_sql is not None:
            out.append(self.unmatched_sql)
        if self.students_sql is not None:
            out.append(self.students_sql)
        return out


def _plan_one(
    cfg: ViewConfig,
    comparison: Comparison,
    *,
    wh: Warehouse,
    cube: Cube,
    build: Build,
    schools: set[str],
) -> _Plan:
    """Compile, expand and fingerprint one comparison's queries; run none that
    bills.

    Only view history runs here, since it decides which queries exist. Whether
    a table both sides read changed during the build is a priced scan, so
    `_compare_all` answers it after the price (`_settle_moved`).
    """
    dates = _date_cubes(cfg)
    dims = [d.cube for d in comparison.dims]
    ex = _Expand(cfg, cube, schools, wh)
    cube_sql, at = ex.cube_sql, ex.at
    fingerprints = _fingerprints(cfg, comparison, ex, build)
    cube_tables: set[str] = set()
    live: set[str] = set()
    cuts: list[_CutPlan] = []
    for cut in _cuts(comparison):
        cube_at = at(cube_sql(cell_query(cfg.view, comparison, cut)), build.end)
        dash_at = at(sheet_query(cfg, comparison, cut), build.start)
        cube_tables |= cube_at.tables
        live |= cube_at.live | dash_at.live
        unfiltered = None
        if comparison.dashboard_filters:
            # The sheet query again without them, to name the cells they drop.
            unfiltered = at(
                sheet_query(cfg, comparison, cut, with_filters=False), build.start
            ).sql
        cuts.append(
            _CutPlan(
                cut_label(cut),
                dash_at.sql,
                wrap_cube(cube_at.sql, cfg.view, dims, dates, comparison.measure),
                unfiltered,
            )
        )

    rows, unmatched_sql, students_sql = None, None, None
    shared: list[str] = []
    if comparison.rows is not None:
        cube_at = at(cube_sql(row_query(cfg.view, comparison), rows=True), build.end)
        dash_at = at(dashboard_rows_sql(cfg, comparison), build.start)
        cube_tables |= cube_at.tables
        live |= cube_at.live | dash_at.live
        shared = sorted(cube_at.tables & dash_at.tables)
        # Unchanged between start and end (`_settle_moved` skips otherwise),
        # so the Cube side reads its shared tables at the start: BigQuery
        # refuses 1 table at 2 moments.
        rows = RowSides(
            cube=cube_at,
            dashboard=dash_at,
            cube_rows_sql=repin(cube_at.sql, shared, build.end, build.start),
            columns=_unique(p.cube for p in _row_pairs(comparison)),
        )
        unmatched_sql = inline_unmatched(cfg, comparison, rows)
        # Only a student column counts students; without one in the grain,
        # every cell's `n_students` stays None, so none is an example cell.
        student = next(
            (
                p.dashboard
                for p in comparison.rows.grain
                if "student" in p.dashboard.lower()
            ),
            None,
        )
        if student:
            students_sql = at(_students_sql(cfg, comparison, student), build.start).sql
    return _Plan(
        comparison=comparison,
        fingerprints=fingerprints,
        cuts=cuts,
        rows=rows,
        unmatched_sql=unmatched_sql,
        shared=shared,
        students_sql=students_sql,
        cube_tables=cube_tables,
        live=live,
    )


def _settle_moved(
    plan: _Plan, known: dict[str, bool], changed: set[str]
) -> Skip | None:
    """Fill `plan.moved` for every table both sides read, from `known` (a held
    checkpoint's answer, or a second fact) else `changed`.

    Returns:
        A skip when such a table changed during the build: BigQuery reads a
        table at 1 moment per query, so the rows cannot be reconciled.
    """
    plan.moved = {t: known.get(t, t in changed) for t in plan.shared}
    if both_moved := [t for t in plan.shared if plan.moved[t]]:
        return Skip(
            plan.comparison.id,
            f"both sides read {', '.join(both_moved)}, which changed during the "
            "build; BigQuery reads a table at 1 moment per query, so the rows "
            "cannot be reconciled at this build",
        )
    return None


def _execute(
    cfg: ViewConfig,
    plan: _Plan,
    *,
    wh: Warehouse,
    build: Build,
    prices: list[float],
) -> _Sides:
    """Run a plan's queries; return its comparison's slice of the run.

    The rows are reconciled in one job that also saves the unmatched ones to
    the scratch dataset (`save_script`), labelled with the view, the moment,
    the comparison and its `checkpoint_fingerprint`.

    Args:
        prices: Each of `plan.queries()`'s dry-run prices, in its order; a
            cut's 2 cell prices are kept as its `cell_sql_usd`. One left over
            means `queries()` and this function no longer agree.
    """
    comparison = plan.comparison
    sides = _Sides(
        cube_tables=set(plan.cube_tables), live=set(plan.live), moved=dict(plan.moved)
    )
    sides.fingerprints[comparison.id] = plan.fingerprints
    price = iter(prices)
    for cut, step in zip(_cuts(comparison), plan.cuts, strict=True):
        sides.cell_sql.setdefault(comparison.id, {})[step.label] = [
            step.dash_sql,
            step.cube_sql,
        ]
        sides.cell_sql_usd.setdefault(comparison.id, {})[step.label] = [
            next(price),
            next(price),
        ]
        cube_rows = wh.rows(step.cube_sql)
        dash_rows = wh.rows(step.dash_sql)
        unfiltered = None
        if step.unfiltered_sql is not None:
            next(price)
            unfiltered = wh.rows(step.unfiltered_sql)
        sides.cells += _cells(
            comparison, cut, dash_rows, cube_rows, comparison.decimals or 0, unfiltered
        )

    if plan.rows is not None:
        next(price)  # the unmatched rows, which stood in for the save script
        flags = cut_flags(comparison) or []
        result = wh.script(
            save_script(
                cfg,
                comparison,
                plan.rows,
                saved.table_sql(saved.table_id(cfg.view, build, comparison.id)),
                saved.labels(
                    cfg.view,
                    build,
                    comparison.id,
                    checkpoint_fingerprint(comparison, plan.fingerprints),
                ),
            )
        )
        sides.groups += reconcile.groups_from(
            comparison.id, result, [label for label, _, _ in flags]
        )
        sides.sql[comparison.id] = (plan.rows.dashboard.sql, plan.rows.cube.sql)
    if plan.students_sql is not None:
        next(price)
        cuts = _cuts(comparison)
        sides.students[comparison.id] = {
            (
                cut_label(cuts[int(r["__cut"])]),
                tuple(_key(r[d.dashboard]) for d in comparison.dims),
            ): r["n_students"]
            for r in wh.rows(plan.students_sql)
        }
    if next(price, None) is not None:
        raise RuntimeError("prices left over: plan.queries() changed")
    return sides


@dataclasses.dataclass(frozen=True)
class RowSides:
    """The row SQL a run reconciled for one comparison, rebuilt for a trace.

    `cube_rows_sql` is Cube's rows read as of the build end, with the tables
    both sides read moved to the build start, as `compare` reconciled them;
    `columns` are the Cube members `wrap_cube` names.
    """

    cube: AsOf
    dashboard: AsOf
    cube_rows_sql: str
    columns: list[str]


def row_sides(
    cfg: ViewConfig,
    comparison: Comparison,
    *,
    wh: Warehouse,
    cube: Cube,
    build: Build,
    schools: set[str],
    fingerprints: dict[str, str],
) -> RowSides:
    """Rebuild the row SQL a run reconciled, refusing when it is not the same SQL.

    Args:
        cfg: The view's config.
        comparison: A comparison with `rows`.
        wh: The warehouse, for view history.
        cube: Cube, for the compiled SQL.
        build: The run's moment.
        schools: The network's school abbreviations (`network_schools`).
        fingerprints: The run's `cube` and `dashboard` fingerprints for it.

    Raises:
        Refusal: The comparison has no rows, or either side's SQL (cells and
            rows, expanded as of the moment) differs from what the run ran.
    """
    if comparison.rows is None:
        raise Refusal(f"comparison {comparison.id!r} has no rows to trace")

    ex = _Expand(cfg, cube, schools, wh)
    cube_at = ex.at(ex.cube_sql(row_query(cfg.view, comparison), rows=True), build.end)
    dash_at = ex.at(dashboard_rows_sql(cfg, comparison), build.start)
    now = _fingerprints(cfg, comparison, ex, build)
    changed = sorted(k for k in now if now[k] != fingerprints.get(k))
    if changed:
        raise Refusal(
            f"comparison {comparison.id!r}: the {' and '.join(changed)} SQL is not "
            "the SQL the run reconciled; run `compare` again, then `sort`"
        )
    shared = sorted(cube_at.tables & dash_at.tables)
    return RowSides(
        cube=cube_at,
        dashboard=dash_at,
        cube_rows_sql=repin(cube_at.sql, shared, build.end, build.start),
        columns=_unique(p.cube for p in _row_pairs(comparison)),
    )


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
        reconcile.clauses_for(columns, dash_sql)
        + reconcile.clauses_for(columns, cube_sql)
    )


def _priced_load(cube: Cube, wh: Warehouse, query: dict) -> list[dict]:
    """`Cube.load`, after a dry run of the SQL Cube compiles for the same query.

    Cube runs that SQL in BigQuery, so call this inside `wh.budget`: the price
    counts toward the cap before the load runs, and toward `wh.spent`.
    """
    wh.price(bind(cube.compiled(query)))
    return cube.load(query)


def _open_counts(
    comparisons: list[Comparison],
    open_groups: list[Group],
    open_gaps: list[Gap],
    open_cells: list[CellDiff],
) -> tuple[Counter, Counter, Counter]:
    """Open groups, gaps and cell differences per measure."""
    measure_of = {c.id: c.measure for c in comparisons}
    groups = Counter(measure_of.get(g.comparison_id) for g in open_groups)
    gaps = Counter(
        measure
        for g in open_gaps
        for measure in {measure_of.get(c) for c in g.comparisons}
    )
    cells = Counter(measure_of.get(d.comparison_id) for d in open_cells)
    return groups, gaps, cells


def verdict(
    cells: dict[str, int], open_groups: int, open_gaps: int, open_cells: int
) -> str:
    """`validated` when every cell passes or is only dashboard-filtered and
    nothing is left to triage, else `differs`.

    Args:
        cells: Cell count per verdict for one measure.
        open_groups: Open row groups.
        open_gaps: Open missing cuts and filters.
        open_cells: Comparisons with open cell differences.

    Returns:
        `validated` or `differs`; a measure with no cells is `differs`.
    """
    clean = bool(cells) and all(v in ("pass", "dashboard_filtered") for v in cells)
    open_items = open_groups or open_gaps or open_cells
    return "validated" if clean and not open_items else "differs"


def _measures(
    comparisons: list[Comparison],
    cells: list[Cell],
    open_groups: list[Group],
    open_gaps: list[Gap],
    open_cells: list[CellDiff],
) -> list[MeasureResult]:
    """One result per measure: its cell counts, open items and verdict."""
    counts: dict[str, Counter] = {}
    for comparison in comparisons:
        mine = [c for c in cells if c.comparison == comparison.id]
        counts.setdefault(comparison.measure, Counter()).update(c.verdict for c in mine)
    groups, gaps, open_cell_counts = _open_counts(
        comparisons, open_groups, open_gaps, open_cells
    )
    return [
        MeasureResult(
            measure,
            verdict(
                dict(found),
                groups.get(measure, 0),
                gaps.get(measure, 0),
                open_cell_counts.get(measure, 0),
            ),
            dict(found),
            groups.get(measure, 0),
            gaps.get(measure, 0),
            open_cell_counts.get(measure, 0),
        )
        for measure, found in counts.items()
    ]


def _extra_sections(cells: list[Cell]) -> str:
    out = ["## Cells", ""]
    out += [
        f"- {c.comparison} {c.cut} {c.key}: dashboard {c.dashboard}, "
        f"Cube {c.cube} ({c.verdict})"
        for c in cells
    ] or ["None."]
    return "\n".join(out) + "\n"


def _browser_cuts(comparisons: list[Comparison]) -> list[str]:
    """Cuts no rebuild check's REST export covered: parameter cuts, and cuts
    added since.

    A rebuild check written before checks recorded their cuts cannot say which
    it covered, so the comparison is listed to rebuild again.
    """
    out = []
    for comparison in comparisons:
        recorded = comparison.rebuild_check.cuts if comparison.rebuild_check else None
        if recorded is None:
            out.append(
                f"{comparison.id}: cuts unknown (the rebuild check records none); "
                "re-run `rebuild-sheet`"
            )
            continue
        out += [
            f"{comparison.id}: {cut_label(cut)} (no export matched it)"
            for cut in _cuts(comparison)
            if cut_label(cut) not in recorded
        ]
    return out


def _unmatched_totals(comparisons: list[Comparison]) -> list[str]:
    """Comparisons whose rebuild check skipped the export's total rows, or
    cannot say."""
    out = []
    for comparison in comparisons:
        skipped = (
            comparison.rebuild_check.totals_skipped
            if comparison.rebuild_check
            else None
        )
        if skipped is None:
            out.append(
                f"{comparison.id}: totals not matched: unknown (the rebuild check "
                "records no count); re-run `rebuild-sheet`"
            )
        elif skipped > 0:
            out.append(f"{comparison.id}: totals not matched: {skipped} rows")
    return out


def _say_caveats(ready: list[Comparison], skips: list[Skip]) -> list[str]:
    """Print what `ready`'s comparisons leave unchecked, and return the totals
    lines for `run.json`.

    Called once every skip is known, so a skipped comparison, whose latest
    result this run does not touch, has neither a totals line
    (`_unmatched_totals`) nor an uncoverable-cells line.
    """
    gone = {s.comparison for s in skips}
    kept = [c for c in ready if c.id not in gone]
    totals = _unmatched_totals(kept)
    for line in totals:
        print(f"{line}.")
    for comparison in kept:
        if why := coverage.unplaceable(comparison):
            print(
                f"Comparison {comparison.id}: its cells cannot be covered ({why}); "
                "its differing cells stay open."
            )
    return totals


def reshape_text(
    shelves: dict[str, Any], reshaped: tableau.Reshaped | None = None
) -> str:
    """`dropped A; added C to rows, D to columns; cleared the filters on E`,
    for a `shelves:` key. With the `reshaped` copy, also the table calcs the
    drop removed and the kept ones that recompute along a changed shelf.
    """
    parts = []
    if shelves.get("drop"):
        parts.append(f"dropped {', '.join(shelves['drop'])}")
    added = [
        f"{', '.join(captions)} to {tableau.SHELF_NAMES[shelf]}"
        for shelf, captions in shelves.get("add", {}).items()
    ]
    if added:
        parts.append(f"added {', '.join(added)}")
    if shelves.get("clear_filters"):
        parts.append(f"cleared the filters on {', '.join(shelves['clear_filters'])}")
    if reshaped is not None:
        if reshaped.removed:
            parts.append(f"removed the table calcs {', '.join(reshaped.removed)}")
        parts += [
            f"recomputes along the new {shelf}: {', '.join(captions)}"
            for shelf, captions in reshaped.recomputed.items()
        ]
    return "; ".join(parts)


def _gaps(comparisons: list[Comparison]) -> tuple[list[Gap], list[str]]:
    """Missing cuts and filters across the rebuild checks, one per kind and
    field.

    Also lists each comparison whose rebuild check predates them.
    """
    found: dict[tuple[str, str], dict[str, Any]] = {}
    unknown = []
    for comparison in comparisons:
        proof = comparison.rebuild_check
        if proof is None or proof.missing_cuts is None or proof.missing_filters is None:
            unknown.append(
                f"{comparison.id}: missing cuts and filters unknown (the rebuild "
                "check predates them); re-run `rebuild-sheet`"
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


def _query_members(query: dict) -> Iterator[str]:
    """Every member a Cube query names, nested `and`/`or` filters included."""
    yield from query.get("measures", [])
    yield from query.get("dimensions", [])
    yield from (t["dimension"] for t in query.get("timeDimensions", []))
    stack = list(query.get("filters", []))
    while stack:
        f = stack.pop()
        if "member" in f:
            yield f["member"]
        stack += f.get("and", []) + f.get("or", [])


def missing_members(
    cfg: ViewConfig, comparisons: Iterable[Comparison], meta: dict
) -> list[str]:
    """The members `compare` would query that Cube's `/meta` lacks, as `<id>: <member>`.

    Read from the queries `compare` sends, so a mapping to a member the model
    dropped or renamed is caught before anything is priced. `/meta` lists what
    this viewer may query: Cube refuses a load of any member it hides.
    """
    known = {
        m["name"]
        for cube in meta.get("cubes", [])
        for kind in ("measures", "dimensions", "segments")
        for m in cube.get(kind) or []
    }
    found: list[str] = []
    for comparison in comparisons:
        queries = [cell_query(cfg.view, comparison, cut) for cut in _cuts(comparison)]
        if comparison.rows is not None:
            queries.append(row_query(cfg.view, comparison))
        names = _unique(m for q in queries for m in _query_members(q))
        found += [f"{comparison.id}: {m}" for m in names if m not in known]
    return found


def _moved_fact_skips(
    cfg: ViewConfig, build: Build, changed: set[str], reads: dict[str, set[str]]
) -> list[Skip]:
    """Skip each comparison whose Cube SQL reads a fact in `cfg.also_facts`
    that is among the `changed` tables.

    The moment is a build of `cfg.fact`: the dashboard is read at its start and
    Cube at its end, so a second fact must hold still in between, or Cube's
    answer mixes 2 moments of it. A second fact has no build of its own to
    pick, so only this check applies to it.

    Args:
        reads: Per comparison id, the tables its Cube SQL reads.
    """
    moved = [f for f in cfg.also_facts if f in changed]
    out = []
    for cid, tables in reads.items():
        if facts := [f for f in moved if f in tables]:
            out.append(
                Skip(
                    cid,
                    f"{', '.join(facts)} changed during the build of {cfg.fact} "
                    f"({utc_literal(build.start)} to {utc_literal(build.end)}); "
                    "Cube reads it at the build end and the dashboard's inputs "
                    "are read at the start, so pick another build with `--moment`",
                )
            )
    return out


# How `workbook_check` starts a line for a workbook Tableau would not answer for.
TABLEAU_ANSWERED = "Tableau answered"

# The keys a comparison needs before `compare` can build its queries.
_NEEDED = ("dashboard_view", "decimals")


def _early_skips(
    cfg: ViewConfig, comparisons: list[Comparison], *, tbl: tableau.Tableau, cube: Cube
) -> list[Skip]:
    """The comparisons `compare` skips before any query, in the order found.

    A comparison is skipped when it lacks a key a run needs (`_NEEDED`), it
    has no rebuild check, its sheet query changed since the check, it maps a
    member Cube's `/meta` lacks (`missing_members`), or its workbook changed
    since the check or Tableau errs on it (`workbook_check`). Each check reads
    only the comparisons no earlier check skipped.
    """
    skips: list[Skip] = []

    def left() -> list[Comparison]:
        gone = {s.comparison for s in skips}
        return [c for c in comparisons if c.id not in gone]

    for c in comparisons:
        if missing := [k for k in _NEEDED if getattr(c, k) in (None, "")]:
            skips.append(Skip(c.id, f"it has no {', '.join(missing)}"))
        elif c.rebuild_check is None:
            skips.append(Skip(c.id, "no rebuild check; run `rebuild-sheet` first"))
        elif c.rebuild_check.sheet_query_fingerprint != sheet_query_fingerprint(cfg, c):
            skips.append(
                Skip(
                    c.id,
                    "the sheet query is not the one its rebuild check covers; run "
                    "`rebuild-sheet` again",
                )
            )
    meta = cube.meta()
    for c in left():
        if missing := missing_members(cfg, [c], meta):
            members = ", ".join(line.removeprefix(f"{c.id}: ") for line in missing)
            skips.append(
                Skip(
                    c.id,
                    f"Cube's model has no member for {members}; fix the mapping, "
                    "then run `rebuild-sheet` again",
                )
            )
    remaining = left()
    stale = workbook_check(cfg, remaining, tbl=tbl, cube=cube)
    for c in remaining:
        if lines := [
            s.removeprefix(f"{c.id}: ") for s in stale if s.startswith(f"{c.id}: ")
        ]:
            what = (
                "the workbook could not be checked"
                if lines[0].startswith(TABLEAU_ANSWERED)
                else "workbook changed since its rebuild check"
            )
            skips.append(Skip(c.id, f"{what}: {'; '.join(lines)}"))
    return skips


# What building a comparison's SQL raises when it cannot be built: a
# BigQuery error comes from a lookup it makes, such as a view's history.
_SQL_ERRORS = (Refusal, CubeRefusal, CubeError, ViewHistoryError, GoogleAPIError)


def _sql_broken(exc: Exception) -> str:
    """Why a comparison's SQL cannot be built: a BigQuery error as fixed words
    with its job and reason code, never its message, which can quote values."""
    if isinstance(exc, GoogleAPIError):
        return f"{SQL_BROKEN}: a lookup failed in BigQuery ({job_failure(exc)})"
    return f"{SQL_BROKEN}: {exc}"


def _bigquery_skip(comparison: str, what: str, exc: GoogleAPIError) -> Skip:
    """A skip for a BigQuery error: fixed words with the job and reason code,
    never BigQuery's message, which can quote values."""
    return Skip(
        comparison,
        f"{what} failed in BigQuery ({job_failure(exc)}); compare it again later",
    )


def _sql_skips(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    *,
    wh: Warehouse,
    cube: Cube,
    schools: set[str],
    now: datetime,
) -> list[Skip]:
    """Each of `comparisons` whose SQL cannot be built today, as
    `stale_comparisons` words it. Compiles and expands only; no query bills."""
    build = Build(now, now, "now")
    out = []
    for c in comparisons:
        try:
            side_fingerprints(cfg, c, wh=wh, cube=cube, build=build, schools=schools)
        except _SQL_ERRORS as exc:
            out.append(Skip(c.id, _sql_broken(exc)))
    return out


# A stopped run resumes on its own within this long of its last checkpoint;
# after it, only with `--resume`, up to time travel's reach.
AUTO_RESUME = timedelta(hours=24)
RESUME_LIMIT = timedelta(days=7)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _run_folder(
    cfg: ViewConfig,
    wh: Warehouse,
    *,
    now: datetime,
    requested: datetime | None,
    resume: bool,
    restart: bool,
    cache_root: Path,
    clock: Callable[[], datetime],
    selected: list[Comparison],
) -> tuple[Path, Build]:
    """The run folder and moment for this `compare`: an unfinished run's, or new.

    With `requested`, the moment is the build it names; its folder's
    checkpoints are reused only when that run is unfinished. Otherwise an
    unfinished run of the view resumes on its own when its last checkpoint is
    under `AUTO_RESUME` old, with `resume` up to `RESUME_LIMIT`, and never past
    it. `restart` clears an unfinished run and starts a new one. A folder a new
    run lands in starts with no checkpoints.

    Raises:
        Refusal: `resume` with nothing to resume, an unfinished run that needs
            `--resume` or `--restart`, or one too old to resume.
    """

    def resuming(u: checkpoints.Unfinished, build: Build) -> None:
        # Only the comparisons this run compares: the others keep their result.
        ids = {c.id for c in selected}
        saved_ids = set(checkpoints.read_all(u.folder)) & ids
        print(
            f"Resuming the unfinished run of {utc_literal(build.start)} to "
            f"{utc_literal(build.end)}: {len(saved_ids)} of {len(ids)} "
            f"comparisons saved, the last at {utc_literal(u.last_at)}."
        )

    if requested is not None:
        build = pick_moment(
            fact_builds(wh, cfg.fact, since=now - WINDOW), now, requested, cfg.fact
        )
        folder = report.run_dir(cache_root, cfg.view, build)
        there = checkpoints.unfinished(folder)
        if restart or there is None or there.fact != cfg.fact:
            checkpoints.clear(folder, keep_spend_of=None if restart else cfg.fact)
        else:
            resuming(there, build)
        return folder, build

    unfinished = checkpoints.find_unfinished(cache_root, cfg.view, cfg.fact)
    if unfinished is not None and restart:
        checkpoints.clear(unfinished.folder)
        unfinished = None
    if unfinished is None and resume:
        raise Refusal(f"no unfinished run of {cfg.view} to resume")
    if unfinished is not None:
        age = clock() - unfinished.last_at
        stamp = report.run_stamp(unfinished.moment)
        if age > RESUME_LIMIT:
            raise Refusal(
                f"{cfg.view}: an unfinished run of {stamp} stopped more than 7 days "
                "ago, past time travel; pass --restart to start a new run"
            )
        if age >= AUTO_RESUME and not resume:
            raise Refusal(
                f"{cfg.view}: an unfinished run of {stamp} stopped "
                f"{age.total_seconds() / 3600:.0f} hours ago; pass --resume to "
                "finish it at that moment, or --restart to start a new run"
            )
        try:
            build = pick_moment([unfinished.moment], now, None, cfg.fact)
        except MomentError as exc:
            raise Refusal(
                f"{cfg.view}: the unfinished run of {stamp} cannot resume: {exc}; "
                "pass --restart to start a new run"
            ) from exc
        resuming(unfinished, build)
        return unfinished.folder, build

    build = pick_moment(
        fact_builds(wh, cfg.fact, since=now - WINDOW), now, None, cfg.fact
    )
    folder = report.run_dir(cache_root, cfg.view, build)
    checkpoints.clear(folder, keep_spend_of=None if restart else cfg.fact)
    return folder, build


ALL_CURRENT = (
    "Every comparison's latest result is current; pass --all to compare every one "
    "again."
)
OTHERS_CURRENT = (
    "Every comparison not skipped has a current latest result; pass --all to "
    "compare every one again."
)


def compare(
    cfg: ViewConfig,
    *,
    wh: Warehouse,
    cube: Cube,
    now: datetime,
    requested: datetime | None,
    max_usd: float,
    cache_root: Path,
    tbl: tableau.Tableau,
    cube_host: str = "",
    resume: bool = False,
    restart: bool = False,
    clock: Callable[[], datetime] = _utcnow,
    ticker: report.Ticker | None = None,
    only: list[str] | None = None,
    every: bool = False,
) -> RunResult | None:
    """Compare a view's comparisons at one fact build and print the validation.

    A validation is each confirmed comparison's latest result, each at its own
    moment (`latest`). `only` compares those comparisons; `every` compares
    every confirmed one; with neither, only those `stale_comparisons` names,
    each printed with its why first. With none, it says so and returns None
    without writing, unless the last `run.json` of `cfg.fact` was composed
    from other results (a run stopped after keeping them): that is composed
    again, at no cost. Each comparison compared replaces its latest result of
    `cfg.fact`'s dataset (`latest.folder`) as it finishes; `run.json` in this
    run's folder is then composed from every confirmed comparison's latest
    result there.

    `cube_host` is printed with `cfg.fact` so the result says what it was
    compared against. A problem with one comparison skips it instead of
    stopping the run: each skip prints `Skipping <id>: <why>.`, the rest are
    compared, and the skipped one keeps its latest result. Before any query,
    a confirmed comparison is skipped when it lacks a key it needs, has no
    rebuild check, its sheet query or workbook changed since the check, or it
    maps a member Cube lacks, or Tableau errs on its workbook
    (`_early_skips`); before the price, when its SQL cannot be built today
    (`_sql_skips`) or at the run's moment, or a dry run it needs fails; after
    the price, when its Cube SQL reads a fact in `also_facts` that changed
    during the build, both sides' rows read a table that did, or one of its
    queries fails in BigQuery, whose spend stays counted (`_compare_all`). A
    BigQuery error is skipped as its job and reason code, never its message,
    which can quote values; only a cap (`CostCapError`) stops the run. The
    skips are kept in `run.json` as `skipped`. Every query a comparison bills
    is priced before the first one runs (`_compare_all`), and `ticker` prints
    a line as each comparison finishes. Each comparison it finishes is
    checkpointed in the run folder; a stopped run started again skips them
    (`_run_folder` says when it resumes). A checkpoint whose comparison entry
    or SQL changed is compared again. `cost_usd` adds what every process spent
    on this run's folder.

    Raises:
        Refusal: `only` names no confirmed comparison; every confirmed
            comparison, or every one `only` names, is skipped; or an
            unfinished run needs `--resume` or `--restart` (`_run_folder`).
        CostCapError: The priced queries would pass `max_usd` or the day's
            cap.
        MomentError: No usable build in the 7-day window.
        CubeRefusal: Cube's SQL would not match a raw rebuild.
    """
    if resume and requested is not None:
        raise Refusal("`--moment` picks the moment itself; drop `--resume`")
    if only and every:
        raise Refusal("`--comparison` and `--all` pick the comparisons; pass one")
    comparisons = [c for c in cfg.comparisons if c.confirmed]
    for skipped in (c for c in cfg.comparisons if not c.confirmed):
        print(f"Skipping comparison {skipped.id!r}: not confirmed.")
    if not comparisons:
        raise Refusal(f"{cfg.view}: no confirmed comparison to run")
    if only and (unknown := sorted(set(only) - {c.id for c in comparisons})):
        raise Refusal(
            f"--comparison: {', '.join(unknown)} is no confirmed comparison of "
            f"{cfg.view}"
        )
    # Every confirmed comparison, before the run folder or any query; a member
    # the model dropped would refuse only after every query ran.
    skips = _early_skips(cfg, comparisons, tbl=tbl, cube=cube)
    _say_skips(skips)
    _refuse_all_skipped(cfg, comparisons, skips)
    ready = [c for c in comparisons if c.id not in {s.comparison for s in skips}]
    for comparison in ready:
        if comparison.rebuild_check:
            print(
                f"Rebuild check for {comparison.id}: matched "
                f"{comparison.rebuild_check.matched_at}."
            )

    results_dir = latest.folder(cache_root / cfg.view, cfg.fact)

    def compose(**kwargs) -> RunResult:
        return _compose(
            cfg,
            comparisons,
            results_dir,
            cube=cube,
            cube_host=cube_host,
            totals=_say_caveats(ready, skips),
            cache_root=cache_root,
            **kwargs,
        )

    with wh.budget(max_usd):
        schools = network_schools(wh)
        sql_skips = functools.partial(
            _sql_skips, cfg, wh=wh, cube=cube, schools=schools, now=now
        )
        results: dict[str, latest.Latest] = {}
        if only:
            selected = [c for c in ready if c.id in only]
            broken = sql_skips(selected)
        elif every:
            selected = ready
            broken = sql_skips(selected)
        else:
            results = latest.read_all(results_dir, cfg.fact)
            whys = stale_comparisons(
                cfg,
                ready,
                results,
                wh=wh,
                cube=cube,
                schools=schools,
                now=now,
            )
            broken = [
                Skip(cid, why)
                for cid, why in whys.items()
                if why.startswith(SQL_BROKEN)
            ]
            for cid, why in whys.items():
                if not why.startswith(SQL_BROKEN):
                    print(f"Comparison {cid}: {why}.")
            selected = [c for c in ready if c.id in whys]
            # Only a result to compare against made `stale_comparisons` build
            # the SQL; build the rest's too.
            broken += sql_skips(
                [c for c in selected if whys[c.id] in (NEVER_COMPARED, ENTRY_CHANGED)]
            )
        # Before the run folder and the price: a skipped comparison's queries
        # are neither priced nor run.
        _say_skips(broken)
        skips += broken
        _refuse_all_skipped(cfg, comparisons, skips)
        selected = [c for c in selected if c.id not in {s.comparison for s in broken}]
        if not selected and only:
            raise Refusal(
                f"{cfg.view}: every comparison asked for was skipped; see the "
                "reasons above"
            )
        if not selected:
            last = _last_run(cfg, cache_root)
            if not _composed_from(last, comparisons, results):
                # A run stopped after keeping its results, before composing.
                print(
                    "Composing run.json again from the latest results: the last "
                    "one predates them. Nothing is compared."
                )
            elif _skip_keys(
                Skip(**s) for s in (last or {}).get("skipped", [])
            ) != _skip_keys(skips):
                # So `ask-owner` lists what is skipped now.
                print(
                    "Composing run.json again to record the comparisons skipped. "
                    "Nothing is compared."
                )
            else:
                _say_caveats(ready, skips)
                print(OTHERS_CURRENT if skips else ALL_CURRENT)
                return None
            newest = max((r.moment for r in results.values()), key=lambda m: m.end)
            folder = report.run_dir(cache_root, cfg.view, newest)
            return compose(
                build=newest,
                folder=folder,
                cost=checkpoints.total_spend(folder),
                skipped=skips,
            )
        folder, build = _run_folder(
            cfg,
            wh,
            now=now,
            requested=requested,
            resume=resume,
            restart=restart,
            cache_root=cache_root,
            clock=clock,
            selected=selected,
        )
        process = f"{clock().isoformat()}-{uuid.uuid4().hex[:8]}"
        checkpoints.start(folder, build, process, cfg.fact)
        try:
            skips += _compare_all(
                cfg,
                selected,
                wh=wh,
                cube=cube,
                build=build,
                folder=folder,
                process=process,
                clock=clock,
                schools=schools,
                results_dir=results_dir,
                ticker=ticker,
            )
        finally:
            checkpoints.record_spend(folder, process, wh.spent)
        cost = checkpoints.total_spend(folder)
    _refuse_all_skipped(cfg, comparisons, skips)
    gone = {s.comparison for s in skips}
    return compose(
        build=build,
        folder=folder,
        cost=cost,
        skipped=skips,
        compared=[c.id for c in selected if c.id not in gone],
    )


def _last_run(cfg: ViewConfig, cache_root: Path) -> dict | None:
    """The view's last readable `run.json` of `cfg.fact`, or None.

    A run saved before runs recorded their fact is no fact's run.
    """
    saved = [
        (path.stat().st_mtime, path)
        for path in (cache_root / cfg.view).glob("*/run.json")
    ]
    for _, path in sorted(saved, reverse=True):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if data.get("fact") == cfg.fact:
            return data
    return None


def _composed_from(
    data: dict | None,
    comparisons: list[Comparison],
    results: dict[str, latest.Latest],
) -> bool:
    """Whether `data` (`_last_run`) was composed from exactly `results`: every
    comparison's moment, entry and SQL fingerprints, and as `missing` the
    comparisons with no result (a skipped one's)."""
    if data is None:
        return False
    held = [c for c in comparisons if c.id in results]
    none = [c.id for c in comparisons if c.id not in results]
    return (data.get("missing") or []) == none and all(
        (data.get("moments") or {}).get(c.id)
        == checkpoints._moment_json(results[c.id].moment)
        and (data.get("entries") or {}).get(c.id) == results[c.id].entry
        and (data.get("fingerprints") or {}).get(c.id)
        == results[c.id].data.get("fingerprints", {}).get(c.id)
        for c in held
    )


def _compose(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    results_dir: Path,
    *,
    cube: Cube,
    cube_host: str,
    totals: list[str],
    cache_root: Path,
    build: Build,
    folder: Path,
    cost: float,
    skipped: Iterable[Skip] = (),
    compared: Iterable[str] = (),
) -> RunResult:
    """Compose, print and save `run.json` in `folder` from every confirmed
    comparison's latest result, in config order; `build` and `cost` are the
    folder's, and `skipped` what this process skipped, whose older results
    compose like the rest. Compiles Cube's measure only; no query bills. Only
    the comparisons in `compared` (this process compared them) refuse when
    Cube cannot compile their measure; the rest compose their older cells.

    Raises:
        Refusal: Two decisions claim one item (`decisions.apply`).
    """
    results = latest.read_all(results_dir, cfg.fact)
    composed = [c for c in comparisons if c.id in results]
    left_out = [c.id for c in comparisons if c.id not in results]
    sides = _Sides(moved={f: False for f in cfg.also_facts})
    for c in composed:
        sides.merge(_Sides.from_json(results[c.id].data))
    changed = sorted(
        {t for c in composed for t in results[c.id].data.get("changed_dims", [])}
    )

    gaps, gaps_unknown = _gaps(comparisons)
    skipped = list(skipped)
    now = set(compared)
    cell_diffs, formula_cells = _cell_diffs(
        cfg, comparisons, sides, cube, frozenset(c.id for c in comparisons) - now
    )
    try:
        applied = decisions.apply(
            cfg.decisions,
            sides.groups,
            sides.fingerprints,
            gaps=gaps,
            cell_diffs=cell_diffs,
        )
    except ValueError as exc:
        raise Refusal(str(exc)) from exc

    clauses = {c.id: _clauses(c, applied.open, sides) for c in comparisons}
    result = RunResult(
        view=cfg.view,
        moment=build,
        cube_host=cube_host,
        fact=cfg.fact,
        measures=_unvalidated(
            _measures(
                comparisons,
                sides.cells,
                applied.open,
                applied.open_gaps,
                applied.open_cells,
            ),
            comparisons,
            left_out,
        ),
        applied=applied,
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
        proofs={
            c.id: c.rebuild_check.matched_at for c in comparisons if c.rebuild_check
        },
        browser_cuts=_browser_cuts(comparisons),
        totals=totals,
        reshaped={c.id: reshape_text(c.shelves) for c in comparisons if c.shelves},
        clauses={k: v for k, v in clauses.items() if v},
        fingerprints=sides.fingerprints,
        decisions_fingerprint=decisions.decisions_fingerprint(cfg.decisions),
        gaps_unknown=gaps_unknown,
        diff_cells=_diff_cells(sides, formula_cells),
        cell_sql=sides.cell_sql,
        cell_sql_usd=sides.cell_sql_usd,
        moments={c.id: results[c.id].moment for c in composed},
        entries={c.id: results[c.id].entry for c in composed},
        missing=left_out,
        skipped=[dataclasses.asdict(s) for s in skipped],
    )
    text = report.render_local(result) + "\n" + _extra_sections(sides.cells)
    print(text)
    saved = report.save_local(result, text, root=cache_root)
    checkpoints._write_text(
        saved.with_name("run.json"),
        json.dumps(dataclasses.asdict(result), default=_json_default, indent=1),
    )
    checkpoints.finish(folder)
    print(f"Saved {saved}")
    return result


NOT_COMPARED = "not compared yet"


def _unvalidated(
    measures: list[MeasureResult], comparisons: list[Comparison], missing: list[str]
) -> list[MeasureResult]:
    """`measures` with any measure of a comparison not compared yet read as
    `NOT_COMPARED`: its cells are unknown, so it cannot be validated."""
    short = {c.measure for c in comparisons if c.id in missing}
    return [
        dataclasses.replace(m, verdict=NOT_COMPARED) if m.measure in short else m
        for m in measures
    ]


def _compare_all(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    *,
    wh: Warehouse,
    cube: Cube,
    build: Build,
    folder: Path,
    process: str,
    clock: Callable[[], datetime],
    schools: set[str],
    results_dir: Path,
    ticker: report.Ticker | None = None,
) -> list[Skip]:
    """Compare each of `comparisons` at `build` and keep each one's result as
    its latest (`latest.write`); return the comparisons it skipped. Call
    inside `wh.budget`.

    A comparison with a checkpoint whose fingerprint still holds is taken from
    it; the rest are planned (`_plan_one`). Before anything that bills, every
    table fingerprint the run needs (the second facts, the tables both sides'
    rows read, Cube's dimension tables) and every planned query is dry-run one
    at a time, and the total is refused when it would pass a cap. The
    fingerprints then run before any comparison query: a comparison whose
    Cube SQL reads a second fact that changed during the build
    (`_moved_fact_skips`), or whose 2 sides' rows both read a table that did
    (`_settle_moved`), is skipped, its priced queries left unrun and its
    latest result kept. The comparisons are compared one at a time, each
    checkpointed (with the spend so far) as it finishes, so a stop loses at
    most the one in progress. Each result keeps the dimension tables it read
    that changed during the build (`changed_dims`). A held checkpoint is kept
    as the latest result only when no later moment's result has replaced it
    since. A comparison whose SQL cannot be built at `build`, whose dry run
    or a table scan it needs fails, or one of whose queries fails in BigQuery
    is skipped and the rest run.

    Raises:
        CostCapError: The priced total would pass the run's or the day's cap,
            or a query would.
    """
    kept = checkpoints.read_all(folder)
    slices: dict[str, tuple[str, _Sides]] = {}
    plans: list[_Plan] = []
    skips: list[Skip] = []
    for comparison in comparisons:
        try:
            if comparison.id in kept:
                fingerprint, data = kept[comparison.id]
                now = checkpoint_fingerprint(
                    comparison,
                    side_fingerprints(
                        cfg, comparison, wh=wh, cube=cube, build=build, schools=schools
                    ),
                )
                if now == fingerprint:
                    slices[comparison.id] = (fingerprint, _Sides.from_json(data))
                    continue
                print(
                    f"Comparison {comparison.id}: its config or SQL changed since "
                    "its saved result; comparing it again."
                )
            plans.append(
                _plan_one(
                    cfg, comparison, wh=wh, cube=cube, build=build, schools=schools
                )
            )
        except _SQL_ERRORS as exc:
            # Built at the run's moment, which `_sql_skips` did not check.
            skips.append(Skip(comparison.id, _sql_broken(exc)))

    # One dry run at a time; one that fails skips the comparison it prices.
    prices: list[list[float]] = []
    for plan in list(plans):
        try:
            prices.append([wh.estimate(sql) for sql in plan.queries()])
        except GoogleAPIError as exc:
            plans.remove(plan)
            skips.append(_bigquery_skip(plan.comparison.id, "its dry run", exc))

    # The second facts have their own check below, and a held checkpoint
    # already answered its shared tables, so neither joins `shared`.
    known = {f: False for f in cfg.also_facts}
    for _, held in slices.values():
        known |= held.moved
    cube_tables = set().union(
        *(p.cube_tables for p in plans), *(h.cube_tables for _, h in slices.values())
    )
    dims = sorted(cube_tables - {cfg.fact, *cfg.also_facts})
    shared = sorted({t for p in plans for t in p.shared if t not in known})
    # Each table once, at both ends of the build, whichever checks need it.
    scanned = _unique([*cfg.also_facts, *shared, *dims])
    scan_usd = 0.0
    for t in list(scanned):
        try:
            scan_usd += sum(
                wh.estimate(fingerprint_sql(t, ts)) for ts in (build.start, build.end)
            )
        except GoogleAPIError as exc:
            # Unscanned, so every comparison that reads it is skipped.
            scanned.remove(t)
            readers = [
                p.comparison.id for p in plans if t in p.cube_tables | set(p.shared)
            ]
            readers += [cid for cid, (_, h) in slices.items() if t in h.cube_tables]
            skips += [
                _bigquery_skip(cid, f"the dry run of a scan of {t}", exc)
                for cid in readers
            ]
    gone = {s.comparison for s in skips}
    slices = {cid: v for cid, v in slices.items() if cid not in gone}
    priced = [
        (p, pr)
        for p, pr in zip(plans, prices, strict=True)
        if p.comparison.id not in gone
    ]
    plans, prices = [p for p, _ in priced], [pr for _, pr in priced]
    _say_skips(skips)
    said = len(skips)
    total = scan_usd + sum(map(sum, prices))
    n = 2 * len(scanned) + sum(map(len, prices))
    print(
        f"Compare: {n} queries, ${total:.2f} (dry run), plus the save script's "
        "temp-table reads, capped per query."
    )
    wh.refuse_past_caps(total)

    changed = set(changed_between(wh, scanned, build.start, build.end))
    skips += _moved_fact_skips(
        cfg,
        build,
        changed,
        {p.comparison.id: p.cube_tables for p in plans}
        | {cid: held.cube_tables for cid, (_, held) in slices.items()},
    )
    gone = {s.comparison for s in skips}
    slices = {cid: v for cid, v in slices.items() if cid not in gone}
    kept_plans = []
    for plan, priced in zip(plans, prices, strict=True):
        if plan.comparison.id in gone:
            continue
        if skip := _settle_moved(plan, known, changed):
            skips.append(skip)
        else:
            kept_plans.append((plan, priced))
    _say_skips(skips[said:])

    def keep(comparison: Comparison, fingerprint: str, one: _Sides) -> None:
        latest.write(
            results_dir,
            comparison.id,
            latest.Latest(
                moment=build,
                fingerprint=fingerprint,
                entry=latest.entry_fingerprint(comparison),
                ran_at=clock().isoformat(),
                data={
                    **one.to_json(),
                    "changed_dims": [t for t in dims if t in changed & one.cube_tables],
                },
                fact=cfg.fact,
            ),
        )

    by_id = {c.id: c for c in comparisons}
    stored = latest.read_all(results_dir, cfg.fact)
    for cid, (fingerprint, held) in slices.items():
        if cid not in stored or stored[cid].moment.end <= build.end:
            keep(by_id[cid], fingerprint, held)
    for plan, priced in kept_plans:
        comparison = plan.comparison
        try:
            one = _execute(cfg, plan, wh=wh, build=build, prices=priced)
        except CostCapError:
            raise
        except GoogleAPIError as exc:
            # Its spend stays counted; the rest still run, so a resume does
            # not stop at it again.
            skip = _bigquery_skip(comparison.id, "a query", exc)
            _say_skips([skip])
            skips.append(skip)
            checkpoints.record_spend(folder, process, wh.spent)
            continue
        fingerprint = checkpoint_fingerprint(comparison, plan.fingerprints)
        checkpoints.write(folder, comparison.id, fingerprint, one.to_json(), clock())
        keep(comparison, fingerprint, one)
        checkpoints.record_spend(folder, process, wh.spent)
        if ticker is not None:
            ticker.say("compare", comparison.id, wh.spent)
    return skips


def _diff_cells(sides: _Sides, formula: set[Cell]) -> list[dict]:
    """Every cell that neither passes nor is dashboard-filtered, for run.json.

    `kind` names the item holding it: `formula` for a cell in `formula`
    (`_cell_diffs`), else `cells`. A run saved before it reads as `cells`.
    """
    return [
        {
            "comparison": c.comparison,
            "cut": c.cut,
            "key": c.key,
            "dims": [list(d) for d in c.dims],
            "dashboard": c.dashboard,
            "cube": c.cube,
            "n_students": sides.students.get(c.comparison, {}).get(
                (c.cut, tuple(v for _, v in c.dims))
            ),
            "kind": "formula" if c in formula else "cells",
        }
        for c in sides.cells
        if c.verdict not in ("pass", "dashboard_filtered")
    ]


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _group(data: dict) -> Group:
    """JSON stores `dims` and `cut_rows` as lists; a group compares by tuples."""
    return Group(
        **{
            **data,
            "dims": tuple(tuple(d) for d in data["dims"]),
            "nulls": tuple(data.get("nulls") or ()),
            "cut_rows": tuple(tuple(c) for c in data.get("cut_rows") or ()),
        }
    )


def _gap(data: dict) -> Gap:
    return Gap(
        **{
            **data,
            "sheets": tuple(data["sheets"]),
            "comparisons": tuple(data["comparisons"]),
        }
    )


def _cell_diff(data: dict) -> CellDiff:
    """A run saved before formula differences split off holds `cells` only."""
    return CellDiff(
        **{**data, "causes": tuple(data["causes"]), "kind": data.get("kind", "cells")}
    )


def _build(data: dict) -> Build:
    return Build(
        datetime.fromisoformat(data["start"]),
        datetime.fromisoformat(data["end"]),
        data["job_id"],
    )


def _run_from_json(data: dict) -> RunResult:
    applied = data["applied"]
    return RunResult(
        view=data["view"],
        moment=_build(data["moment"]),
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
            open_cells=[_cell_diff(d) for d in applied.get("open_cells", [])],
            quiet_cells=[
                (Decision(**d), _cell_diff(c))
                for d, c in applied.get("quiet_cells", [])
            ],
            quiet_gaps=[
                (Decision(**d), _gap(g)) for d, g in applied.get("quiet_gaps", [])
            ],
            causes=[Decision(**d) for d in applied.get("causes", [])],
        ),
        live_sources=data["live_sources"],
        changed_dims=data["changed_dims"],
        scopes=data["scopes"],
        cost_usd=data["cost_usd"],
        proofs=data["proofs"],
        browser_cuts=data["browser_cuts"],
        totals=data.get("totals", []),
        reshaped=data.get("reshaped", {}),
        clauses=data["clauses"],
        fingerprints=data.get("fingerprints", {}),
        decisions_fingerprint=data.get("decisions_fingerprint", ""),
        gaps_unknown=data.get("gaps_unknown", []),
        dashboard_filters=data.get("dashboard_filters", []),
        diff_cells=data.get("diff_cells", []),
        cell_sql=data.get("cell_sql", {}),
        cell_sql_usd=data.get("cell_sql_usd", {}),
        cube_host=data.get("cube_host", ""),
        fact=data.get("fact", ""),
        moments={k: _build(v) for k, v in data.get("moments", {}).items()},
        entries=data.get("entries", {}),
        missing=data.get("missing", []),
        skipped=data.get("skipped", []),
    )


# What `reapply` rebuilds the run's full findings from; a run saved without
# any of them predates re-applying.
_REAPPLY_KEYS = (
    "open",
    "quiet",
    "open_gaps",
    "quiet_gaps",
    "open_cells",
    "quiet_cells",
)


def _saved_run(cfg: ViewConfig, cache_root: Path) -> tuple[dict, Path]:
    """The latest `run.json` of `cfg.fact` as JSON, and its path.

    The latest run is the `run.json` of the fact the command was given
    (`--fact-dataset` names a dev build's) written last, whatever moment it
    read. A run saved before runs recorded their fact is no fact's run, as in
    `_last_run`: it never stands in for one.

    Raises:
        Refusal: The view has no saved run of `cfg.fact`; the message names
            the fact of the latest run there is, if any, else says the saved
            run is an older validator's.
    """
    saved = sorted(
        (cache_root / cfg.view).glob("*/run.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    other, legacy = None, None
    for path in saved:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        fact = data.get("fact") if isinstance(data, dict) else None
        if not fact:
            legacy = legacy or path
        elif fact == cfg.fact:
            return data, path
        else:
            other = other or fact
    if other:
        raise Refusal(
            f"{cfg.view}: no saved run of {cfg.fact}; the latest run read "
            f"{other}, which this command does not use. `compare` it, or pass "
            "--fact-dataset to read that build"
        )
    if legacy:
        raise _older(cfg, legacy)
    raise Refusal(f"{cfg.view}: no saved run; `compare` it first")


def _older(cfg: ViewConfig, run_json: Path) -> Refusal:
    return Refusal(
        f"{cfg.view}: the saved run {run_json} was written by an older "
        "validator; `compare` it again"
    )


def _require_nulls(data: dict) -> None:
    """Refuse a run saved before groups recorded which values were NULL.

    Such a run reads a NULL group-by value as empty text, so an explanation
    finds none of that group's rows: the run, not the explanation, is at fault.
    """
    applied = data.get("applied") or {}
    groups = [*applied.get("open", []), *(g for _, g in applied.get("quiet", []))]
    if any("nulls" not in g for g in groups):
        moment = (data.get("moment") or {}).get("start", "<moment>")
        raise Refusal(
            "this run predates NULL-aware groups; run again "
            f"(`compare --moment {moment}`)"
        )


def _reapplicable(cfg: ViewConfig, cache_root: Path) -> tuple[RunResult, Path]:
    """The latest saved run, refused when it lacks what re-applying reads."""
    data, run_json = _saved_run(cfg, cache_root)
    if "fingerprints" not in data or any(
        k not in data.get("applied", {}) for k in _REAPPLY_KEYS
    ):
        raise _older(cfg, run_json)
    try:
        return _run_from_json(data), run_json
    except (KeyError, TypeError) as exc:
        raise _older(cfg, run_json) from exc


def _apply_saved(cfg: ViewConfig, saved: RunResult) -> Applied:
    """Sort everything the saved run found by the file's decisions."""
    was = saved.applied
    try:
        return decisions.apply(
            cfg.decisions,
            was.open + [g for _, g in was.quiet],
            saved.fingerprints,
            gaps=was.open_gaps + [g for _, g in was.quiet_gaps],
            cell_diffs=was.open_cells + [d for _, d in was.quiet_cells],
        )
    except ValueError as exc:
        raise Refusal(str(exc)) from exc


def check_claims(cfg: ViewConfig, cache_root: Path) -> None:
    """Refuse decisions that would claim one item twice in the saved run.

    Called before decisions are written, since a file whose decisions overlap
    makes both `compare` and `reapply` refuse. With no saved run this validator
    can re-apply to, there is nothing to check against and nothing refuses.

    Raises:
        Refusal: Two decisions claim the same group, gap or formula
            difference, or a cause decision disagrees with the `group`
            decision closing a group its explanation covers (`sort.check_closed`).
    """
    try:
        saved, run_json = _reapplicable(cfg, cache_root)
    except Refusal:
        return
    applied = _apply_saved(cfg, saved)
    _check_closed(cfg, dataclasses.replace(saved, applied=applied), run_json)


def _check_closed(cfg: ViewConfig, run: RunResult, run_json: Path) -> None:
    try:
        sort.check_closed(run, run_json, cfg.decisions)
    except Refusal as exc:
        raise Refusal(f"{cfg.view}: {exc}") from exc


def reapply(cfg: ViewConfig, cache_root: Path) -> RunResult:
    """Apply the file's decisions to the view's latest saved run, offline.

    Recording a decision changes no data, so the saved run's groups, gaps,
    cell differences and SQL fingerprints are re-sorted by the current
    decisions as `compare` would sort them; a decision whose fingerprints differ
    from the run's still lands in `reconfirm`. Rewrites `run.json` and
    `result.md` and runs no query. The verdict is read again from the cells
    and the open counts. Clauses stay as the run computed them, over the
    groups open then, so a group a deleted decision reopens may show no clause
    until the next `compare`.

    Raises:
        Refusal: The view has no saved run, the run predates what re-applying
            needs, two decisions claim the same item, or a cause decision
            disagrees with the `group` decision closing a group its explanation
            covers (`sort.check_closed`). Nothing is rewritten.
    """
    saved, run_json = _reapplicable(cfg, cache_root)
    applied = _apply_saved(cfg, saved)
    _check_closed(cfg, dataclasses.replace(saved, applied=applied), run_json)

    groups, gaps, cells = _open_counts(
        cfg.comparisons, applied.open, applied.open_gaps, applied.open_cells
    )
    result = dataclasses.replace(
        saved,
        applied=applied,
        measures=_unvalidated(
            [
                dataclasses.replace(
                    m,
                    verdict=verdict(
                        m.cells,
                        groups.get(m.measure, 0),
                        gaps.get(m.measure, 0),
                        cells.get(m.measure, 0),
                    ),
                    open_groups=groups.get(m.measure, 0),
                    open_gaps=gaps.get(m.measure, 0),
                    open_cells=cells.get(m.measure, 0),
                )
                for m in saved.measures
            ],
            cfg.comparisons,
            saved.missing,
        ),
        decisions_fingerprint=decisions.decisions_fingerprint(cfg.decisions),
    )
    # The cells section needs every cell the run held; decisions
    # never change them, so the saved report's copy is kept.
    old = run_json.with_name("result.md")
    old_text = old.read_text() if old.exists() else ""
    at = old_text.find("\n## Cells\n")
    tail = old_text[at + 1 :] if at != -1 else ""
    text = report.render_local(result) + ("\n" + tail if tail else "")
    report.save_local(result, text, root=cache_root).with_name("run.json").write_text(
        json.dumps(dataclasses.asdict(result), default=_json_default, indent=1)
    )
    return result


# --- ask-owner ---------------------------------------------------------------


def latest_run(cfg: ViewConfig, cache_root: Path) -> tuple[RunResult, Path]:
    """Return the view's latest saved run and the `run.json` it came from.

    The latest run is the `run.json` of `cfg.fact` written last, whatever
    moment it read (`_saved_run`).

    Raises:
        Refusal: The view has no saved run of `cfg.fact`, its saved run is
            in a shape this validator cannot read or predates NULL-aware
            groups, or its decisions changed since the run (a run saved
            before runs recorded them counts as changed).
    """
    data, run_json = _saved_run(cfg, cache_root)
    try:
        run_result = _run_from_json(data)
    except (KeyError, TypeError) as exc:
        raise _older(cfg, run_json) from exc
    _require_nulls(data)
    if run_result.decisions_fingerprint != decisions.decisions_fingerprint(
        cfg.decisions
    ):
        raise Refusal(
            f"{cfg.view}: the decisions changed since the saved run "
            f"{run_json}; `reapply` it, or `compare` it again with --all"
        )
    return run_result, run_json


BODY_WARN_CHARS = report.BODY_WARN_CHARS


def ask_owner(
    configs: list[ViewConfig],
    domain: str,
    cache_root: Path,
    now: datetime | None = None,
    view_files: list[Path] | None = None,
    comments: list[str] | None = None,
    json_file: Path | None = None,
) -> str:
    """Return the review-issue body from each view's latest saved run.

    Reads only the local cache: each run and its triage (see
    `sort.checked_sort`), matching triage items to decisions by their stubs,
    and to cause decisions by the causes the sort explained. What is ready is
    asked; what is not settled yet (items still in `investigate`, and
    comparisons missing, stale or skipped, `sort.comparisons_waiting`) is
    listed under "Still with the analyst" and never asked.
    Nothing is posted; a question with no triage evidence, and a body near
    GitHub's cap, are named on stderr.

    Args:
        configs: The views to review.
        domain: The domain whose owner reviews.
        cache_root: The run cache.
        now: The current time, to say whether a hand check's pinned SQL still
            runs; defaults to the clock.
        view_files: Each config's validation file, in order: stored explanation
            paths are relative to its directory.
        comments: Given, receives the follow-up comments a long body's
            Reproduce blocks move to (`report.render_review_issue`).
        json_file: Given, the questions JSON is written there (`reviews/`
            beside the validation file) and the body links it at the commit
            that holds it, instead of carrying it.

    Raises:
        Refusal: A view has no usable saved run (see `latest_run`), or its
            triage is missing, stale, unreadable, or has a cause decision and
            a `group` decision disagreeing (see `sort.checked_sort`). With
            `json_file`: the file is new or changed, or its commit is not
            pushed (it is written; commit and push it, then review again).
    """
    saved = [latest_run(cfg, cache_root) for cfg in configs]
    runs = [run for run, _ in saved]
    # Stored explanation paths are relative to each validation file's directory.
    bases = [f.parent for f in view_files] if view_files else [None] * len(configs)
    proven = {
        run.view: sort.checked_sort(run, run_json, cfg.decisions, base)
        for (run, run_json), cfg, base in zip(saved, configs, bases, strict=True)
    }
    found = {view: sort.posted_sort(loaded) for view, loaded in proven.items()}
    still = report.still_with_analyst(
        [u for run in runs for u in sort.unsettled(run, found[run.view])],
        {
            run.view: sort.comparisons_waiting(cfg, run, proven[run.view])
            for run, cfg in zip(runs, configs, strict=True)
        },
    )
    # One question per unanswered owner cause, over the groups it decides.
    causes = {
        run.view: sort.cause_asks(
            run, proven[run.view], cfg.decisions, sort.doc_leads(cfg)
        )
        for run, cfg in zip(runs, configs, strict=True)
    }
    definitions = {
        cfg.view: {c.id: c.definitions for c in cfg.comparisons if c.definitions}
        for cfg in configs
    }
    sources = {
        cfg.view: explanation_source(f)
        for cfg, f in zip(configs, view_files or [], strict=False)
    }
    questions = answers.questions_json(
        runs,
        configs,
        definitions,
        found,
        now or datetime.now(timezone.utc),
        causes,
        sources,
    )
    # The analyst's other calls, which the body reports without asking.
    decided = {
        run.view: sort.cause_asks(run, proven[run.view], cfg.decisions, owner=False)
        for run, cfg in zip(runs, configs, strict=True)
    }
    link = None
    if json_file is not None:
        link = _review_file(Path(json_file), report.posted_json(questions))
    body = report.render_review_issue(
        domain, runs, definitions, questions, causes, comments, decided, link, still
    )
    if len(body) > BODY_WARN_CHARS:
        # stderr, so the warning never lands in the issue body.
        print(
            f"warning: the body is {len(body):,} characters; GitHub refuses an "
            "issue body over 65,536, so review fewer views at a time",
            file=sys.stderr,
        )
    for q in questions:
        if not q["evidence"]:
            # stderr, so the note never lands in the issue body.
            print(
                f"{q['id']}: no triage evidence; `sort` the view to add it",
                file=sys.stderr,
            )
    if waiting := report.untasked(d for cfg in configs for d in cfg.decisions):
        # stderr, so the reminder never lands in the issue body.
        print(
            'After posting, fill in `task: "#<issue>"` on: ' + ", ".join(waiting),
            file=sys.stderr,
        )
    return body


def review_file(view_files: list[Path], configs: list[ViewConfig], domain: str) -> Path:
    """Where a review's questions JSON is kept: `reviews/` beside the first
    validation file, named for its view, or for the domain across views."""
    name = configs[0].view if len(configs) == 1 else _slug(domain)
    return Path(view_files[0]).parent / "reviews" / f"{name}.json"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "review"


def _review_file(path: Path, data: list[dict]) -> str:
    """The questions JSON's link at the commit that holds it.

    Compared by content, so the commit hook's formatting is no change.

    Raises:
        Refusal: The file was new or held other questions (now written), or
            it is not committed and pushed as it stands.
    """
    try:
        held = json.loads(path.read_text())
    except (OSError, ValueError):
        held = None
    if held != data:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
        raise Refusal(
            f"wrote {path}: commit and push it, then run `ask-owner` again; the "
            "issue links it at that commit"
        )
    link = committed_link(path)
    if link is None:
        raise Refusal(
            f"{path} is not committed and pushed as it stands: commit and push "
            "it, then run `ask-owner` again"
        )
    return link


def committed_link(path: Path) -> str | None:
    """The GitHub link to `path` at HEAD, or None.

    None unless the file is tracked with no change since HEAD and HEAD is on
    a remote branch (a pushed commit), so the link opens once posted and
    keeps opening after the branch is gone.
    """
    base = path.parent
    try:
        top = Path(_git(base, "rev-parse", "--show-toplevel"))
        changed = _git(base, "status", "--porcelain", "--", path.name)
        tracked = _git(base, "ls-files", "--", path.name)
        sha = _git(base, "rev-parse", "HEAD")
        pushed = _git(base, "branch", "-r", "--contains", sha)
        remote = _git(base, "remote", "get-url", "origin")
        relative = path.resolve().relative_to(top.resolve())
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None
    found = _GITHUB.search(remote)
    if changed or not tracked or not pushed or not found:
        return None
    return f"https://github.com/{found['repo']}/blob/{sha}/{relative.as_posix()}"


_GITHUB = re.compile(r"github\.com[:/](?P<repo>[\w.-]+/[\w.-]+?)(?:\.git)?/?$")


def _git(directory: Path, *args: str) -> str:
    # trunk-ignore(bandit/B603,bandit/B607): git from PATH with a static argv and no shell
    done = subprocess.run(
        ["git", "-C", str(directory), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def explanation_source(view_file: Path) -> answers.ExplanationSource:
    """Where a validation file's stored explanations live: its repo path and the
    branch URL of its directory, for an owner's Reproduce block.

    Outside a git checkout, a GitHub remote or a branch, the link is left out.
    The remote's address is read for its `owner/repo` only, never copied.
    """
    view_file = Path(view_file)
    base = view_file.parent
    try:
        top = Path(_git(base, "rev-parse", "--show-toplevel"))
        branch = _git(base, "branch", "--show-current")
        remote = _git(base, "remote", "get-url", "origin")
        relative = view_file.resolve().relative_to(top.resolve())
    except (OSError, ValueError, subprocess.CalledProcessError):
        return answers.ExplanationSource(str(view_file), base)
    found = _GITHUB.search(remote)
    blob = None
    if found and branch:
        blob = (
            f"https://github.com/{found['repo']}/blob/{branch}/"
            f"{relative.parent.as_posix()}"
        )
    return answers.ExplanationSource(relative.as_posix(), base, blob)


# --- rebuild-sheet -----------------------------------------------------------


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
    it in `Measure Names` and holding it in `Measure Values`. `field` names
    one of those fields, or a column beside them (a measure on another shelf),
    which repeats on every field's row of a mark, so each mark is kept once. A
    wide export comes back as is.

    Raises:
        Refusal: The export is long and `field` is unset or names neither a
            field nor a column in it; the message lists both.
    """
    if not rows or MEASURE_NAMES not in rows[0]:
        return rows
    names = sorted({r[MEASURE_NAMES] for r in rows})
    others = [h for h in rows[0] if h not in (MEASURE_NAMES, MEASURE_VALUES)]
    choices = f"its fields are {', '.join(names)}; its columns are {', '.join(others)}"
    if not field:
        raise Refusal(f"the export has one row per field; set sheet_field ({choices})")
    if field in names:
        return [
            {**{k: r[k] for k in others}, field: r[MEASURE_VALUES]}
            for r in rows
            if r[MEASURE_NAMES] == field
        ]
    if field in others:
        marks = dict.fromkeys(tuple((k, r[k]) for k in others) for r in rows)
        return [dict(mark) for mark in marks]
    raise Refusal(f"sheet_field {field!r} is not in the export; {choices}")


@dataclasses.dataclass(frozen=True)
class SheetGaps:
    """Sheet fields with no Cube member, by caption. Values are never read."""

    cuts: list[str]
    filters: list[str]
    restricting: list[str]
    # Caption to why the field needs no Cube member: `copy of <mapped caption>`
    # or `display switch on <parameter caption>`.
    notes: dict[str, str] = dataclasses.field(default_factory=dict)
    # Caption to the datasource column, for a plain field (never a calculation).
    columns: dict[str, str] = dataclasses.field(default_factory=dict)


_WHOLE_REF = re.compile(r"\[(?P<name>[^\]]+)\]")
_PARAMETER_REF = re.compile(r"\[Parameters\]\.\[(?P<name>[^\]]+)\]")
_STRING_LITERAL = re.compile(r"'[^']*'|\"[^\"]*\"")
_FIELD_REF = re.compile(r"\[[^\]]+\]")
_COMMENT = re.compile(r"//[^\n]*")


def _parameter_only(formula: str) -> re.Match | None:
    """The first parameter a formula reads, when it reads no other field.

    Comments go before string literals, so an apostrophe in a comment cannot
    pair with one on a later line and hide the field between them.
    """
    bare = _STRING_LITERAL.sub("", _COMMENT.sub("", formula))
    if _FIELD_REF.search(_PARAMETER_REF.sub("", bare)):
        return None
    return _PARAMETER_REF.search(bare)


def _parameter_captions(twb_xml: str) -> dict[str, str]:
    """Map each parameter's bare name to its caption."""
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    return {
        (col.get("name") or "").strip("[]"): col.get("caption") or ""
        for ds in root.iter("datasource")
        if ds.get("name") == "Parameters"
        for col in ds.findall("column")
    }


def sheet_gaps(twb_xml: str, comparison: Comparison) -> SheetGaps:
    """Name the sheet's cuts and filters that have no Cube member.

    A field counts as having one when the comparison maps it anywhere: a dim,
    a filter, or a row grain or value. Aggregated fields, `Measure Names`,
    user filters and fields built on the viewer's identity are skipped.

    Also returns `notes` (a plain copy of a mapped field, or a calculation that
    reads only parameters) and `columns` (the datasource column behind each
    plain missing field).
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
    groups = finder.group_fields(ws)
    mapped_caption_of = {p.dashboard: c for c, p in comparison.filters.items()}

    def field_of(ref: str) -> str | None:
        name = finder.filter_field(ref, groups)
        if name is None:
            return None
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

    calcs = {c.name.strip("[]"): c.formula for c in finder.calculated_fields(twb_xml)}
    parameters = _parameter_captions(twb_xml)
    notes: dict[str, str] = {}
    columns: dict[str, str] = {}
    for name in cuts | filters:
        formula = (calcs.get(name) or "").strip()
        # A group or bin is no datasource column: triage cannot value-check it.
        if name not in calcs and name not in groups:
            columns[caption.get(name, name)] = name
        elif (param := _parameter_only(formula)) is not None:
            notes[caption.get(name, name)] = (
                f"display switch on {parameters.get(param['name']) or param['name']}"
            )
        elif (whole := _WHOLE_REF.fullmatch(formula)) is not None:
            ref = whole["name"]
            if ref in mapped or caption.get(ref) in mapped_captions:
                shown = mapped_caption_of.get(ref) or caption.get(ref, ref)
                notes[caption.get(name, name)] = f"copy of {shown}"

    return SheetGaps(
        captions(cuts), captions(filters), captions(restricting), notes, columns
    )


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
    """Turn export rows into sheet-query-shaped cells; count total and summed rows.

    An export shows a dim's alias (grade 0 as `K`), so each value goes back
    through the sheet's aliases. A sheet with totals exports them as rows whose
    dim reads `All`; those are dropped, unless the sheet query has a real `All`
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
    # A dual axis exports one row per pane, identical in every column: count
    # it once. A row that differs anywhere still reads as a repeat. Summed
    # split rows keep every row, since 2 rows of a split field the export
    # does not show can match in every column.
    seen: set[tuple] = set()
    for r in rows:
        whole = tuple(sorted((k, str(v)) for k, v in r.items()))
        if whole in seen and comparison.split_rows != "sum":
            continue
        seen.add(whole)
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
) -> tuple[str, str, list[ET.Element], list[dict], list[dict], tableau.Snapshot]:
    """Export a comparison's sheet once per workbook, sheet, cuts, parameter
    values and reshape.

    Returns:
        The workbook XML, the same with the sheet reshaped (`shelves`), the
        reshaped sheet's columns, the cuts a REST export takes, the cuts only
        a browser can check, and the snapshot.
    """
    _require(comparison, "workbook", "sheet")
    workbook, sheet = comparison.workbook or "", comparison.sheet or ""
    twb = tbl.download_twb(workbook)
    parameters, shelves = comparison.parameters, comparison.shelves
    try:
        if parameters:
            tableau.set_parameters(twb, parameters)
        shaped = tableau.set_shelves(twb, sheet, shelves).xml if shelves else twb
    except ValueError as exc:
        raise Refusal(f"comparison {comparison.id!r}: {exc}") from exc
    columns = _sheet_columns(shaped, sheet)
    measures = [c.get("name") or "" for c in columns if c.get("role") == "measure"]
    if not measures:
        raise Refusal(f"sheet {sheet!r} lists no measure")
    exportable, browser = tableau.split_cuts(_cuts(comparison), twb)
    if not exportable:
        raise Refusal(f"comparison {comparison.id!r} has no cut a REST export can take")
    captures = {} if captures is None else captures

    def edit(x: str) -> str:
        # The reshape goes first, so the format drop sees any column it copied.
        x = tableau.set_shelves(x, sheet, shelves).xml if shelves else x
        x = tableau.expose_sheet(tableau.drop_number_formats(x, measures), sheet)
        # A field shown only behind a parameter value exports once the copy
        # carries that value.
        return tableau.set_parameters(x, parameters) if parameters else x

    key = (
        workbook,
        sheet,
        tuple(cut_label(cut) for cut in exportable),
        tuple(sorted(parameters.items())),
        json.dumps(shelves, sort_keys=True),
    )
    if key not in captures:
        try:
            captures[key] = tbl.capture(workbook, sheet, exportable, edit)
        except (LookupError, tableau.RefreshMovedError) as exc:
            raise Refusal(f"cannot export {sheet!r}: {exc}") from exc
    return twb, shaped, columns, exportable, browser, captures[key]


def rebuild_sheet_headers(
    cfg: ViewConfig,
    path: Path,
    comparison_id: str,
    *,
    tbl: tableau.Tableau,
    captures: dict[tuple, tableau.Snapshot] | None = None,
) -> None:
    """Print each exported cut's column headers, and the fields a long export
    names, without probing or writing anything. A reshaped comparison first
    prints the copy's rows and columns.
    """
    comparison = _comparison_by_id(cfg, path, comparison_id)
    twb, shaped, _, exportable, _, snap = _capture(comparison, tbl, captures)
    if comparison.shelves:
        sheet = comparison.sheet or ""
        shape = finder.sheet_shape(shaped, sheet)
        reshaped = tableau.set_shelves(twb, sheet, comparison.shelves)
        calcs = reshape_text({}, reshaped)
        print(
            f"{comparison.id} reshaped: rows {', '.join(shape.rows) or 'none'}; "
            f"columns {', '.join(shape.cols) or 'none'}"
            + (f"; {calcs}" if calcs else "")
        )
    for cut, rows in zip(exportable, snap.exports, strict=True):
        headers = list(rows[0]) if rows else []
        print(
            f"{comparison.id} cut {cut_label(cut)}: {', '.join(headers) or 'no rows'}"
        )
        if MEASURE_NAMES in headers:
            names = sorted({r[MEASURE_NAMES] for r in rows})
            print(f"  {MEASURE_NAMES}: {', '.join(names)}")


def rebuild_sheet(
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
) -> tableau.RebuildResult:
    """Rebuild a comparison's sheet in SQL, match it to the sheet's export, and
    write `rebuild_check:`.

    Failures and browser cuts print to the terminal only: a count per reason
    and a few samples, with the full list in `failures_dir` when given.
    `captures` keeps each sheet's export across calls, so comparisons on one
    sheet and cuts share a capture.

    Raises:
        Refusal: The comparison is unknown or incomplete, an exportable cut
            has no rows on a side, or the cells did not match.
    """
    comparison = _comparison_by_id(cfg, path, comparison_id)
    _require(comparison, "workbook", "sheet", "dashboard_view", "decimals")
    twb, shaped, columns, exportable, browser, snap = _capture(
        comparison, tbl, captures
    )
    if snap.refresh_started < now - REBUILD_WINDOW:
        raise Refusal(
            f"the extract refreshed at {snap.refresh_started}, outside the 7 days "
            "of warehouse history; rebuild after the next refresh"
        )

    exports: list[dict] = []
    probes: list[dict] = []
    totals_skipped = 0
    with wh.budget(max_usd):
        for cut, rows in zip(exportable, snap.exports, strict=True):
            label = cut_label(cut)
            probe_rows = wh.rows(
                _as_of(sheet_query(cfg, comparison, cut), snap.refresh_started, wh).sql
            )
            if not rows or not probe_rows:
                side = "export" if not rows else "sheet query"
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
        proof = tableau.match_export(comparison, exports, probes, twb_xml=twb, now=now)
    except ValueError as exc:
        raise Refusal(f"comparison {comparison.id!r}: {exc}") from exc
    for cut in browser:
        print(f"Check in the browser: {cut_label(cut)}")
    if not proof.matched:
        print(
            f"Rebuild check failed for {comparison.id} ({proof.cells} cells matched):"
        )
        _print_failures(comparison.id, proof.failures, failures_dir)
        raise Refusal(f"comparison {comparison.id!r} did not match; nothing written")

    # The copy's shelves: a dropped field is no longer a missing cut.
    gaps = sheet_gaps(shaped, comparison)
    for kind, names in (("cuts", gaps.cuts), ("filters", gaps.filters)):
        if names:
            print(f"Sheet {kind} with no Cube member: {', '.join(names)}")

    write_rebuild_check(
        path,
        comparison.id,
        {
            "fingerprint": proof.fingerprint,
            "cells": proof.cells,
            "matched_at": proof.matched_at.isoformat(),
            "workbook_updated_at": tbl.workbook_updated(
                comparison.workbook or ""
            ).isoformat(),
            "sheet_query_fingerprint": sheet_query_fingerprint(cfg, comparison),
            # `workbook_check` reads a republish that changed neither this nor
            # `fingerprint` as no change to the sheet.
            "source_fingerprint": tableau.source_fingerprint(
                twb, comparison.sheet or ""
            ),
            # `compare` lists every other cut as one to check in the browser.
            "cuts": [cut_label(cut) for cut in exportable],
            # `compare` lists these rows as totals no rebuild check covered.
            "totals_skipped": totals_skipped,
            # The parameter values the copy showed; the fingerprint covers them.
            **(
                {"parameters": dict(comparison.parameters)}
                if comparison.parameters
                else {}
            ),
            # The reshape the copy carried; `compare` names it, since the check
            # covers the reshaped grain, not the sheet's own.
            **({"shelves": comparison.shelves} if comparison.shelves else {}),
            # `compare` lists these as missing cuts and filters to sort.
            "missing_cuts": gaps.cuts,
            "missing_filters": gaps.filters,
            "restricting_filters": gaps.restricting,
            # `sort` reads these offline: a copy or display switch needs no
            # member; a plain column can be value-checked.
            "filter_notes": gaps.notes,
            "missing_columns": gaps.columns,
        },
    )
    print(
        f"Matched {comparison.id}: {proof.cells} cells; wrote rebuild_check to {path}."
    )
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
        path = failures_dir / f"rebuild-failures-{comparison_id}.txt"
        path.write_text("\n".join(failures) + "\n")
        print(f"  Full list: {path}")


def workbook_check(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    *,
    tbl: tableau.Tableau,
    cube: Cube,
) -> list[str]:
    """List the comparisons whose sheet or Cube members changed since their
    rebuild check.

    A workbook published after the check is downloaded once and its sheet
    compared by what the check covers: `fingerprint` (the sheet's formulas
    and filters) and `source_fingerprint` (its datasources' connection and
    filters). A republish that changed neither is printed as such and not
    listed. A rebuild check without `source_fingerprint` cannot rule out a datasource
    change, so it is stale after any republish. A matched comparison that maps a
    member Cube's `/meta` no longer lists is stale too, and one whose workbook
    Tableau errs on reads `TABLEAU_ANSWERED` and its error.

    Args:
        cfg: The view's config.
        comparisons: The comparisons to check.
        tbl: Tableau, for each workbook's publish time and file.
        cube: Cube, for its `/meta` members.

    Returns:
        One line per problem, each starting with its comparison's id and
        ending in what to do.
    """
    proven = [c for c in comparisons if c.rebuild_check is not None]
    stale = [
        f"{line}, which Cube's model no longer has; fix the mapping and re-run "
        "`rebuild-sheet`"
        for line in missing_members(cfg, proven, cube.meta())
    ]
    twbs: dict[str, str] = {}
    for comparison in comparisons:
        if not comparison.workbook:
            continue
        proof = comparison.rebuild_check
        if proof is None:
            stale.append(f"{comparison.id}: no rebuild check")
            continue
        try:
            updated = tbl.workbook_updated(comparison.workbook)
            if comparison.workbook not in twbs and proof.workbook_updated_at:
                if updated > datetime.fromisoformat(proof.workbook_updated_at):
                    twbs[comparison.workbook] = tbl.download_twb(comparison.workbook)
        except TSC.ServerResponseError as exc:
            # One workbook's error is its comparisons' alone.
            stale.append(
                f"{comparison.id}: {TABLEAU_ANSWERED} {exc.code} {exc.summary}; "
                "try again, or re-run `rebuild-sheet` if the workbook moved"
            )
            continue
        if not proof.workbook_updated_at:
            stale.append(
                f"{comparison.id}: rebuild check has no workbook_updated_at; "
                "re-run `rebuild-sheet`"
            )
            continue
        if updated <= datetime.fromisoformat(proof.workbook_updated_at):
            continue
        published = (
            f"workbook published {updated.isoformat()}, after the rebuild check's "
            f"{proof.workbook_updated_at}"
        )
        twb, sheet = twbs[comparison.workbook], comparison.sheet or ""
        try:
            formulas = tableau.formula_fingerprint(twb, sheet)
            sources = tableau.source_fingerprint(twb, sheet)
        except ValueError as exc:
            stale.append(
                f"{comparison.id}: {published}, and {exc}; re-run `rebuild-sheet`"
            )
            continue
        if formulas != proof.fingerprint:
            stale.append(
                f"{comparison.id}: {published}; the sheet's formulas or filters "
                "changed; re-run `rebuild-sheet`"
            )
        elif not proof.source_fingerprint:
            stale.append(
                f"{comparison.id}: {published}; the sheet's formulas are unchanged, "
                "but the rebuild check predates the datasource check; re-run "
                "`rebuild-sheet` once"
            )
        elif sources != proof.source_fingerprint:
            stale.append(
                f"{comparison.id}: {published}; a datasource's connection or "
                "filters changed; re-run `rebuild-sheet`"
            )
        else:
            print(
                f"{comparison.id}: republished {updated.isoformat()}, sheet unchanged"
            )
    return stale


# --- find-field --------------------------------------------------------------


def _outer_from(sql: str) -> int:
    """Index of the first `FROM` outside parentheses and quoted text, or -1.

    `EXTRACT(YEAR FROM x)` and `TRIM(BOTH ' ' FROM x)` hold a `FROM` of their
    own that does not start the query's FROM clause.
    """
    depth = 0
    quote = ""
    i = 0

    while i < len(sql):
        ch = sql[i]

        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "'\"`":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and re.match(r"FROM\b", sql[i:], re.IGNORECASE):
            if i == 0 or not (sql[i - 1].isalnum() or sql[i - 1] == "_"):
                return i

        i += 1

    return -1


def _measure_expression(sql: str, view: str, measure: str) -> str:
    """The SELECT expression of a measure-only compiled query, alias dropped."""
    end = _outer_from(sql)
    head = sql if end < 0 else sql[:end]
    head = re.sub(r"^\s*SELECT\s+", "", head, flags=re.IGNORECASE)
    return head.replace(f"`{view}__{measure}`", "").strip()


def find_field(
    cfg: ViewConfig,
    measure: str,
    *,
    cube: Cube,
    tbl: tableau.Tableau | None,
    exposures_path: Path,
    only: list[str],
    caption: str | None = None,
    limit: int | None = finder.TOP_N,
    twb_path: Path | None = None,
) -> list[finder.Candidate]:
    """Print workbook fields ranked against a measure, then each listed sheet's
    shape: shelves, export form, displayed decimals and filters.

    Calculated fields and aggregated raw fields both rank; a formula that uses a
    code group shows its codes. `caption` boosts the dashboard's name for the
    measure; `limit` None prints every candidate. With `twb_path` the one local
    workbook is read instead of the exposures' downloads, and `tbl` is unused.
    """
    compiled = cube.compiled({"measures": [_member(cfg.view, measure)]})
    member_sql = _measure_expression(compiled.sql, cfg.view, measure)

    found: list[finder.Candidate] = []
    twbs: dict[str, str] = {}
    workbooks = (
        [(str(twb_path), twb_path.name, twb_path.read_text(encoding="utf-8"))]
        if twb_path is not None
        else _exposure_workbooks(tbl, exposures_path, only)
    )
    for luid, label, twb in workbooks:
        twbs[luid] = twb
        found += finder.rank(
            measure,
            member_sql,
            finder.calculated_fields(twb) + finder.aggregated_fields(twb),
            workbook_luid=luid,
            workbook_label=label,
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


def _exposure_workbooks(
    tbl: tableau.Tableau | None, exposures_path: Path, only: list[str]
) -> Iterator[tuple[str, str, str]]:
    """Download each Tableau exposure's workbook: luid, label and XML."""
    if tbl is None:
        raise Refusal("find-field needs a Tableau session or a local --twb")
    exposures = finder.tableau_exposures(exposures_path)
    if exposures.skipped:
        print(
            f"Skipped exposures without a luid or models: {', '.join(exposures.skipped)}"
        )
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
        yield exposure.luid, exposure.label, twb


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
