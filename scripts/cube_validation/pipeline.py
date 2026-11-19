"""The shared core of the commands, which live in their own modules.

`cli.py` parses arguments and builds the clients; the functions here and in
`compare`, `results`, `rebuild` and `review` take those clients as arguments
so tests can pass fakes. This module holds what several of them share: the
filters and queries, cells, the SQL fingerprints and checkpoint slices, the row
sides, the skip and refusal types, and `find-field`. The dashboard side is read
as of a fact build's start and Cube as of its end. Every BigQuery query runs
inside `Warehouse.budget`, and only aggregates come back: row-level
comparisons run inside BigQuery through `reconcile.reconcile_script`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import zipfile
from collections.abc import Callable, Iterable, Iterator
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import tableauserverclient as TSC
from google.api_core.exceptions import GoogleAPIError

from . import decisions
from . import find_field as finder
from . import reconcile, report, tableau
from .bq import ViewHistoryError, Warehouse, job_failure
from .config import (
    WEEK_END_KEY,
    ColumnPair,
    Comparison,
    RowSpec,
    ViewConfig,
    fingerprint_data,
)
from .cube_client import (
    Compiled,
    Cube,
    CubeError,
    CubeRefusal,
    bind,
    drop_limit,
    refuse_unless_safe,
    sort_school_filters,
)
from .moment import Build
from .reconcile import Group
from .timetravel import PROJECT, AsOf, as_of, repin, utc_literal


class Refusal(RuntimeError):
    """A command stopped on purpose; the message says why."""


def rows_of(comparison: Comparison, to: str = "") -> RowSpec:
    """The comparison's `rows`, refusing a comparison with none.

    Args:
        comparison: The comparison.
        to: What the rows were wanted for, ending the refusal ("explain"
            refuses "has no rows to explain"); none ends it at "has no rows".

    Raises:
        Refusal: The comparison has no `rows`.
    """
    if comparison.rows is None:
        why = f" to {to}" if to else ""
        raise Refusal(f"comparison {comparison.id!r} has no rows{why}")
    return comparison.rows


@dataclasses.dataclass(frozen=True)
class Skip:
    """A comparison `compare` leaves out, and why; it keeps its latest result."""

    comparison: str
    why: str


# --- filters and queries -----------------------------------------------------


def comparison_cuts(comparison: Comparison) -> list[dict[str, Any]]:
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


def member_name(view: str, name: str) -> str:
    return name if "." in name else f"{view}.{name}"


def _cut_cube_filters(
    view: str, comparison: Comparison, cut: dict[str, Any]
) -> list[dict]:
    return [
        {
            "member": member_name(view, comparison.filters[caption].cube),
            "operator": "equals",
            "values": [_cube_text(v) for v in _values(value)],
        }
        for caption, value in effective_filters(comparison, cut).items()
    ]


def scope_cube_filters(view: str, comparison: Comparison) -> list[dict]:
    return [
        {**f, "member": member_name(view, f["member"])}
        for f in reconcile.scope_filters(comparison)
    ]


def lit(value: Any) -> str:
    """A BigQuery literal, escaped the way Cube's parameters are bound."""
    return bind(Compiled("?", [value], []))


def _column_predicate(column: str, value: Any) -> str:
    direct = [v for v in _values(value) if isinstance(v, (bool, int, float))]
    text = [str(v) for v in _values(value) if not isinstance(v, (bool, int, float))]
    parts = []
    if text:
        parts.append(f"CAST({column} AS STRING) IN ({', '.join(map(lit, text))})")
    if direct:
        parts.append(f"{column} IN ({', '.join(map(lit, direct))})")
    return parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")"


SQL_COMPARE = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}


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


def dashboard_filter_sql(entry: dict[str, Any]) -> str:
    """One `dashboard_filters` entry as SQL; `not_equals` keeps nulls, as Cube's does."""
    column, operator = entry["dashboard"], entry["operator"]
    if operator == "set":
        return f"{column} IS NOT NULL"
    if (days := entry.get(WEEK_END_KEY)) is not None:
        return f"{column} {SQL_COMPARE[operator]} {_week_end_sql(days)}"
    if operator in SQL_COMPARE:
        return f"{column} {SQL_COMPARE[operator]} {lit(entry['values'][0])}"
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
        parts += [dashboard_filter_sql(e) for e in comparison.dashboard_filters]
    return " AND ".join(parts) or "TRUE"


def _any_cut_predicate(comparison: Comparison) -> str:
    """OR of every cut, so a row-level reconcile counts each row once. The
    comparison's `dashboard_filters` are left out."""
    preds = [
        dashboard_predicate(comparison, cut, with_filters=False)
        for cut in comparison_cuts(comparison)
    ]
    if "TRUE" in preds:
        return "TRUE"
    return preds[0] if len(preds) == 1 else " OR ".join(f"({p})" for p in preds)


def _varying_captions(comparison: Comparison) -> list[str]:
    """The captions whose value differs across the comparison's cuts.

    A caption with one value in every cut (a default no cut changes) cannot
    split the cells.
    """
    chosen = [effective_filters(comparison, cut) for cut in comparison_cuts(comparison)]
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
    cells; `row_pairs` makes each of them a row column on both sides.
    """
    cuts = comparison_cuts(comparison)
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
    per_cut = [
        _cut_cube_filters(view, comparison, cut) for cut in comparison_cuts(comparison)
    ]
    if any(not f for f in per_cut):
        return []
    if len(per_cut) == 1:
        return per_cut[0]
    return [{"or": [{"and": f} for f in per_cut]}]


def cell_query(view: str, comparison: Comparison, cut: dict[str, Any]) -> dict:
    """Return the Cube query for a comparison's cells under one cut."""
    return {
        "measures": [member_name(view, comparison.measure)],
        "dimensions": [member_name(view, d.cube) for d in comparison.dims],
        "filters": _cut_cube_filters(view, comparison, cut)
        + scope_cube_filters(view, comparison),
    }


def row_pairs(comparison: Comparison) -> list[ColumnPair]:
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


def unique(names: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(names))


def row_query(view: str, comparison: Comparison) -> dict:
    """Return the ungrouped Cube query for a comparison's rows over every cut."""
    return {
        "dimensions": [
            member_name(view, c) for c in unique(p.cube for p in row_pairs(comparison))
        ],
        "filters": _any_cut_cube_filters(view, comparison)
        + scope_cube_filters(view, comparison),
        "ungrouped": True,
    }


def dashboard_ref(comparison: Comparison) -> str:
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


def date_cubes(cfg: ViewConfig) -> set[str]:
    return {cfg.time_dimension} if cfg.time_dimension else set()


def grouped_dims(
    cfg: ViewConfig, comparison: Comparison, first: int = 1
) -> tuple[list[str], str]:
    """The dims as the sheet query selects them, and its GROUP BY.

    A time dim is selected as its DATE under its own name. The GROUP BY names
    the dims by position, the first at column `first`; it is empty with no dims.
    """
    dates = date_cubes(cfg)
    select = [
        f"DATE({d.dashboard}) AS {d.dashboard}" if d.cube in dates else d.dashboard
        for d in comparison.dims
    ]
    group = (
        " GROUP BY " + ", ".join(str(i + first) for i in range(len(select)))
        if select
        else ""
    )
    return select, group


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
    seen = _row_dates(cfg, comparison)
    cols = [
        f"DATE({name}) AS {name}" if is_date else name for name, is_date in seen.items()
    ] + [
        f"COALESCE({dashboard_filter_sql(e)}, FALSE) AS {flag}"
        for e, (flag, _) in zip(
            comparison.dashboard_filters, filter_flags(comparison), strict=True
        )
    ]
    # The ranking reads the row SQL's own columns: its date columns are
    # already DATEs and its filter flags are columns.
    return _rows_sql(
        comparison,
        ", ".join(cols),
        keys={name: name for name in seen},
        kept=[flag for flag, _ in filter_flags(comparison)],
    )


def dashboard_scoped_rows_sql(cfg: ViewConfig, comparison: Comparison) -> str:
    """Return every column of the dashboard rows the reconcile reads.

    The rows are `dashboard_rows_sql`'s: any cut, with no `dashboard_filters`
    applied, inside `rows.dashboard_scope`, and cut by `rows.reduce` to the
    latest per grain key, ranked the same way. Every column of the dashboard
    view is kept, so the sheet query can read them in place of the view.
    """
    seen = _row_dates(cfg, comparison)
    # Every column is selected raw, so the sheet query's own `DATE(day) AS day`
    # reads the same input; only the partition keys read a date column as its
    # DATE, as the reconcile's row SQL keys it. Each filter is read inline.
    return _rows_sql(
        comparison,
        "*",
        keys={
            name: f"DATE({name})" if is_date else name for name, is_date in seen.items()
        },
        kept=[
            f"COALESCE({dashboard_filter_sql(e)}, FALSE)"
            for e in comparison.dashboard_filters
        ],
    )


def _row_dates(cfg: ViewConfig, comparison: Comparison) -> dict[str, bool]:
    """Each dashboard column the row SQL selects, and whether it is a date."""
    dates = date_cubes(cfg)
    seen: dict[str, bool] = {}
    for p in row_pairs(comparison):
        seen.setdefault(p.dashboard, p.cube in dates)
    return seen


def _rows_sql(
    comparison: Comparison, select: str, *, keys: dict[str, str], kept: list[str]
) -> str:
    """The dashboard rows of every cut inside `rows.dashboard_scope`, cut by
    `rows.reduce` to the latest per grain key within each cut.

    Args:
        comparison: The comparison.
        select: The columns to select from the dashboard view.
        keys: Per row column, how the ranking reads it; the grain's and the
            varying captions' make the partition.
        kept: Per `dashboard_filters` entry, as the ranking reads whether it
            keeps the row.

    Returns:
        A SELECT over the dashboard view.
    """
    spec = comparison.rows
    where = _any_cut_predicate(comparison)
    if scope := spec.dashboard_scope if spec else []:
        parts = [where, *map(dashboard_filter_sql, scope)]
        where = " AND ".join(f"({p})" for p in parts)
    reduce = spec.reduce if spec else {}
    if reduce:
        select += f", {reduce['by']} AS __reduce_by"
    # trunk-ignore(bandit/B608): identifiers are validated in config.py and values are bound or literal-escaped
    sql = f"SELECT {select} FROM {dashboard_ref(comparison)} WHERE {where}"
    if spec is None or not reduce:
        return sql
    split = [comparison.filters[c].dashboard for c in _varying_captions(comparison)]
    partition = ", ".join(
        keys[c] for c in unique([p.dashboard for p in spec.grain] + split)
    )
    order = (
        f"({''.join(f'{k} AND ' for k in kept)}TRUE) DESC, __reduce_by DESC"
        if kept
        else "__reduce_by DESC"
    )
    return (
        # trunk-ignore(bandit/B608): identifiers are validated in config.py
        f"SELECT * EXCEPT (__reduce_by) FROM ({sql}) "
        f"QUALIFY RANK() OVER (PARTITION BY {partition} ORDER BY {order}) = 1"
    )


def filter_flags(comparison: Comparison) -> list[tuple[str, str]]:
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
    rows: str | None = None,
) -> str:
    """Return the sheet query over the dashboard rows under one cut, before time
    travel.

    `sheet_query` is an aggregate over the rows; `sheet_query_sql` is a template whose
    `{rows}`, `{where}` and `{dims}` are filled here. `with_filters` False
    leaves out the `dashboard_filters`, to name the cells they drop. `rows`,
    when given, is read in place of every row of the dashboard view; left
    out, the SQL is the one `sheet_query_fingerprint` covers.
    """
    if rows is None:
        # trunk-ignore(bandit/B608): identifiers are validated in config.py and values are bound or literal-escaped
        rows = f"SELECT * FROM {dashboard_ref(comparison)}"
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
    select, group = grouped_dims(cfg, comparison)
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


def value_key(value: Any) -> str:
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


# --- SQL fingerprints and row sides ------------------------------------------


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


def checked_as_of(sql: str, ts: datetime, wh: Warehouse) -> AsOf:
    """`as_of`, with its fail-closed refusals (an unknown table, a deep view)."""
    try:
        return as_of(sql, ts, wh)
    except ValueError as exc:
        raise Refusal(f"cannot read the SQL as of {utc_literal(ts)}: {exc}") from exc


def _masked(at: AsOf, ts: datetime) -> str:
    """The expanded SQL with the moment taken out, so only definitions remain."""
    return at.sql.replace(utc_literal(ts), "<moment>")


@dataclasses.dataclass
class Sides:
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

    def merge(self, other: Sides) -> None:
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
    def from_json(cls, data: dict) -> Sides:
        """The slice `to_json` wrote, with its tuples restored."""

        def pairs(dims) -> tuple:
            return tuple(tuple(p) for p in dims)

        return cls(
            cube_tables=set(data["cube_tables"]),
            live=set(data["live"]),
            cells=[Cell(**{**c, "dims": pairs(c["dims"])}) for c in data["cells"]],
            groups=[group_from_json(g) for g in data["groups"]],
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


class Expand:
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
            self._expanded[(sql, ts)] = checked_as_of(sql, ts, self._wh)
        return self._expanded[(sql, ts)]


def expanded_fingerprints(
    cfg: ViewConfig, comparison: Comparison, ex: Expand, build: Build
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
    return expanded_fingerprints(cfg, comparison, Expand(cfg, cube, schools, wh), build)


def checkpoint_fingerprint(comparison: Comparison, fingerprints: dict[str, str]) -> str:
    """What a comparison's saved work holds for: its config entry, as
    `config.fingerprint_data` reads it, and both sides' SQL. Any edit to
    either makes the saved work stale."""
    return hashlib.sha256(
        json.dumps(
            [
                fingerprint_data(comparison),
                fingerprints,
            ],
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()


def reconcile_args(
    cfg: ViewConfig, comparison: Comparison, sides: RowSides
) -> tuple[tuple, dict]:
    """The positional and keyword arguments every row query of a comparison
    takes (`reconcile.reconcile_script`, `unmatched_rows_sql`)."""
    flags = cut_flags(comparison) or []
    args = (
        wrap_cube(sides.cube_rows_sql, cfg.view, sides.columns, date_cubes(cfg), None),
        sides.dashboard.sql,
        comparison.rows,
        group_dims(comparison),
    )
    return args, {
        "filters": filter_flags(comparison),
        "cuts": [(c, d) for _, c, d in flags],
    }


def inline_unmatched(cfg: ViewConfig, comparison: Comparison, sides: RowSides) -> str:
    """The rows `save_script` saves, as one query with no table, for a dry run."""
    args, kwargs = reconcile_args(cfg, comparison, sides)
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
    rows_of(comparison, "trace")

    ex = Expand(cfg, cube, schools, wh)
    cube_at = ex.at(ex.cube_sql(row_query(cfg.view, comparison), rows=True), build.end)
    dash_at = ex.at(dashboard_rows_sql(cfg, comparison), build.start)
    now = expanded_fingerprints(cfg, comparison, ex, build)
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
        columns=unique(p.cube for p in row_pairs(comparison)),
    )


def priced_load(cube: Cube, wh: Warehouse, query: dict) -> list[dict]:
    """`Cube.load`, after a dry run of the SQL Cube compiles for the same query.

    Cube runs that SQL in BigQuery, so call this inside `wh.budget`: the price
    counts toward the cap before the load runs, and toward `wh.spent`.
    """
    wh.price(bind(cube.compiled(query)))
    return cube.load(query)


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


# What building a comparison's SQL raises when it cannot be built: a
# BigQuery error comes from a lookup it makes, such as a view's history.
SQL_ERRORS = (Refusal, CubeRefusal, CubeError, ViewHistoryError, GoogleAPIError)


def sql_broken(exc: Exception) -> str:
    """Why a comparison's SQL cannot be built: a BigQuery error as fixed words
    with its job and reason code, never its message, which can quote values."""
    if isinstance(exc, GoogleAPIError):
        return f"{report.SQL_BROKEN}: a lookup failed in BigQuery ({job_failure(exc)})"
    return f"{report.SQL_BROKEN}: {exc}"


def group_from_json(data: dict) -> Group:
    """JSON stores `dims` and `cut_rows` as lists; a group compares by tuples."""
    return Group(
        **{
            **data,
            "dims": tuple(tuple(d) for d in data["dims"]),
            "nulls": tuple(data.get("nulls") or ()),
            "cut_rows": tuple(tuple(c) for c in data.get("cut_rows") or ()),
        }
    )


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


def measure_expression(sql: str, view: str, measure: str) -> str:
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
    compiled = cube.compiled({"measures": [member_name(cfg.view, measure)]})
    member_sql = measure_expression(compiled.sql, cfg.view, measure)

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
    # A local workbook's views are not on the server: published is not checked.
    views = tbl.view_names if twb_path is None and tbl is not None else None
    _print_sheets(found, twbs, views)
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


def _print_sheets(
    found: list[finder.Candidate],
    twbs: dict[str, str],
    views: Callable[[str], set[str]] | None = None,
) -> None:
    """Print each listed sheet's shape. `views` lists a workbook's views on
    the server; without it (a local workbook) published is not checked."""
    sheets = list(
        dict.fromkeys(
            (c.workbook_luid, c.workbook_label, s) for c in found for s in c.worksheets
        )
    )
    if not sheets:
        return
    print("\nSheets:" if views else f"\nSheets ({tableau.NOT_CHECKED}):")
    roots = {
        luid: finder.parse_workbook(twbs[luid])
        for luid in dict.fromkeys(luid for luid, _, _ in sheets)
    }
    # Per workbook, its published sheets or why they could not be asked.
    published: dict[str, set[str] | str] = {}
    for luid, root in roots.items():
        if views is None:
            continue
        try:
            published[luid] = tableau.published_sheets(root, views(luid))
        except TSC.ServerResponseError as exc:
            published[luid] = f"Tableau answered {exc.code} {exc.summary}"
    for luid, label, sheet in sheets:
        shape = finder.sheet_shape(roots[luid], sheet)
        print(
            f"  {sheet} ({label}): rows {', '.join(shape.rows) or 'none'}; "
            f"columns {', '.join(shape.cols) or 'none'}"
        )
        seen = published.get(luid)
        if isinstance(seen, str):
            print(f"    published: not checked: {seen}")
        elif seen is not None and sheet not in seen:
            print(f"    {tableau.NOT_PUBLISHED}")
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
