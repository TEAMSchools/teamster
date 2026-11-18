"""Recompute a comparison's differing cells on the rows both sides matched.

A cell that still differs once both sides read only matched rows differs by
its formula, not by its rows. Matched rows are the rows the reconcile matched,
minus every saved unmatched key: the grain keys the run's own `joined` files
`match` with both sides present, less any key it also files otherwise (an
unmatched duplicate, a row a dashboard filter drops) and any key the run saved
as unmatched. Rows the reconcile never saw, such as out-of-scope or non-latest
daily rows, are never matched, so they can never read as a formula difference.
The SQL builders and `verdicts` are pure; `plan` looks up what the SQL needs
and `run_job` runs it, for `sort`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from google.api_core.exceptions import GoogleAPIError
from sqlglot import exp
from sqlglot.errors import SqlglotError

from . import coverage, cube_client, explain, pipeline, reconcile, trace
from .bq import CostCapError, ViewHistoryError, Warehouse, job_failure
from .config import Comparison, RowSpec, ViewConfig
from .cube_client import Cube, CubeError, CubeRefusal
from .moment import Build
from .report import RunResult, mask
from .timetravel import _NOT_ALIAS, PROJECT, repin

# A cell the check could not recompute closes by coverage under this label,
# followed by one of the reasons below.
NOT_COMPARED = "formulas not compared"
REWRITE_DIFFERS = "the rewrite does not reproduce the run's cells"
NO_ROWS = "no rows both sides hold"
SAVED_GONE = "its saved rows are gone or of another run; compare it again"
SQL_MOVED = "its SQL changed since the run; compare it again"
CUBE_REFUSED = "Cube refused its SQL; sort again"
NOT_COMPOSED = "the run is not composed from the latest results; compare it again"
OUTSIDE = "not run: outside --comparison; sort it"
CAPPED = "a cap stopped it; sort again with a higher --max-usd"
# An error no reason above names, from code that builds the check's SQL.
UNBUILT = "its SQL could not be built; see the terminal"
# The reasons a check that ran its queries can give; any other is a failure.
_RAN = (REWRITE_DIFFERS, NO_ROWS)


def bigquery_refused(exc: GoogleAPIError) -> str:
    """The reason for a BigQuery error: its job and reason code only, since its
    message can quote a value."""
    return f"BigQuery refused it ({job_failure(exc)}); sort again"


class NotCompared(Exception):
    """The formula check cannot run; the text is one of this module's reasons."""


# A cell as `run.diff_cells` names it: its cut label and its key.
CellRef = tuple[str, str]


@dataclass
class Check:
    """One comparison's formula check, kept beside the result it checked.

    `fingerprint` is that result's `checkpoint_fingerprint`, so a newer result
    never reads an older check. `formula` holds the cells that still differ
    on matched rows, `coverage` those that agree there, and `not_compared`
    the cells left to coverage per reason. `lines` name each formula cell's
    cut, dims and both values: local only, never posted.
    """

    comparison: str
    fingerprint: str
    formula: list[CellRef] = field(default_factory=list)
    coverage: list[CellRef] = field(default_factory=list)
    not_compared: dict[str, list[CellRef]] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        """The check as JSON data, cells as `[cut, key]` pairs."""
        return {
            "comparison": self.comparison,
            "fingerprint": self.fingerprint,
            "formula": [list(c) for c in self.formula],
            "coverage": [list(c) for c in self.coverage],
            "not_compared": {
                why: [list(c) for c in cells]
                for why, cells in self.not_compared.items()
            },
            "lines": list(self.lines),
        }

    @classmethod
    def from_json(cls, data: dict) -> Check:
        """The check `to_json` wrote, its cells as tuples again."""

        def refs(cells: list) -> list[CellRef]:
            return [(cut, key) for cut, key in cells]

        return cls(
            comparison=data["comparison"],
            fingerprint=data["fingerprint"],
            formula=refs(data["formula"]),
            coverage=refs(data["coverage"]),
            not_compared={why: refs(c) for why, c in data["not_compared"].items()},
            lines=list(data["lines"]),
        )


def _values(
    rows: list[dict], names: list[str]
) -> tuple[dict[tuple, float | None], set[tuple]]:
    """Each row's `value` by its cut and its dims under `names`, keyed as
    `compare._cells` keys a cut's cells, and the keys more than 1 row holds."""
    values: dict[tuple, float | None] = {}
    repeated: set[tuple] = set()
    for r in rows:
        key = (r["__cut"], tuple(pipeline.value_key(r[n]) for n in names))
        if key in values:
            repeated.add(key)
        values[key] = None if r["value"] is None else float(r["value"])
    return values, repeated


def verdicts(
    comparison: Comparison,
    fingerprint: str,
    cells: list[dict],
    dash: list[dict],
    cube: list[dict],
    dash_self: list[dict],
    cube_self: list[dict],
) -> Check:
    """Decide each differing cell from both sides' recomputed values.

    In order: a cell any of the 4 results holds more than 1 row for, or a
    self-check that does not reproduce the run's value for the cell, on either
    side, is `REWRITE_DIFFERS`; no matched value on either side is `NO_ROWS`;
    values that agree at the comparison's `decimals` leave the cell to
    coverage; else the cell differs by its formula.

    Args:
        comparison: The comparison checked.
        fingerprint: The checked result's `checkpoint_fingerprint`.
        cells: Its differing cells, as `run.diff_cells` holds them.
        dash: The dashboard side on matched rows (`dashboard_side_sql`).
        cube: Cube's side on matched rows (`cube_side_sql`).
        dash_self: The dashboard side with nothing removed.
        cube_self: Cube's side with nothing removed.

    Returns:
        The check, each cell in exactly one of its piles.
    """
    decimals = comparison.decimals or 0
    on_dash = [d.dashboard for d in comparison.dims]
    on_cube = [d.cube for d in comparison.dims]
    read = {
        "dashboard": (_values(dash, on_dash), _values(dash_self, on_dash)),
        "cube": (_values(cube, on_cube), _values(cube_self, on_cube)),
    }
    sides = {side: (kept[0], whole[0]) for side, (kept, whole) in read.items()}
    repeated = set().union(*(k[1] | w[1] for k, w in read.values()))
    check = Check(comparison.id, fingerprint)
    for cell in cells:
        ref = (cell["cut"], cell["key"])
        at = (cell["cut"], tuple(pipeline.value_key(v) for _, v in cell["dims"]))
        if at in repeated or any(
            reconcile.cell_verdict(whole.get(at), cell[side], decimals) != "pass"
            for side, (_, whole) in sides.items()
        ):
            check.not_compared.setdefault(REWRITE_DIFFERS, []).append(ref)
            continue
        d, c = sides["dashboard"][0].get(at), sides["cube"][0].get(at)
        if d is None and c is None:
            check.not_compared.setdefault(NO_ROWS, []).append(ref)
        elif reconcile.cell_verdict(d, c, decimals) == "pass":
            check.coverage.append(ref)
        else:
            check.formula.append(ref)
            check.lines.append(
                f"{cell['cut']} {cell['key']}: dashboard {d}, Cube {c} on matched rows"
            )
    return check


def _rows(comparison: Comparison) -> RowSpec:
    """The comparison's `rows`; the check needs a row grain to match on."""
    if comparison.rows is None:
        raise pipeline.Refusal(f"comparison {comparison.id!r} has no rows")
    return comparison.rows


def _keyed(keys: list[str]) -> str:
    """One row's key from its grain keys; NULL when the first, the student, is."""
    fields = ", ".join(f"{k} AS k{i}" for i, k in enumerate(keys))
    return f"IF({keys[0]} IS NULL, NULL, TO_JSON_STRING(STRUCT({fields})))"


def key_sql(columns: list[str], dates: list[bool]) -> str:
    """The key of one row from its grain columns, keyed as the reconcile keys
    them.

    Beyond the reconcile's keys, a date column is first cast to DATE here, so
    a TIMESTAMP and the DATE of the same day key alike.

    Args:
        columns: The row's grain columns, the student first.
        dates: Per column, whether it is a date grain.

    Returns:
        A string expression; NULL when the first column's key is NULL.
    """
    read = [
        f"CAST({c} AS DATE)" if is_date else c
        for c, is_date in zip(columns, dates, strict=True)
    ]
    return _keyed(reconcile._grain_keys(read))


def matched_ctes(
    cfg: ViewConfig,
    comparison: Comparison,
    sides: pipeline.RowSides,
    saved_table: str,
) -> str:
    """The `WITH` prefix whose last CTE, `__matched`, holds the matched keys.

    The reconcile's `joined` is rebuilt from the run's row SQL, so its row
    sets are the ones the run reconciled.

    Args:
        cfg: The view's config.
        comparison: A comparison with `rows`.
        sides: The row SQL the run reconciled for it.
        saved_table: The comparison's saved unmatched rows, as SQL names the
            table.

    Returns:
        CTEs ending in `__matched AS (SELECT __key ...)`, with no final SELECT.

    Raises:
        pipeline.Refusal: The comparison has no `rows`.
    """
    n = len(_rows(comparison).grain)
    args, kwargs = pipeline.reconcile_args(cfg, comparison, sides)
    ctes, _ = reconcile._joined(*args, keys=True, moved=True, **kwargs)
    # `__k*` are already the reconcile's grain keys.
    joined_key = _keyed([f"__k{i}" for i in range(n)])
    # The saved grain is typed as the reconcile typed it, as `__k*` were, so
    # it is keyed as is: a date grain is already a DATE on both sides.
    plain = [False] * n
    dash_key = key_sql([f"__gd{i}" for i in range(n)], plain)
    cube_key = key_sql([f"__gc{i}" for i in range(n)], plain)
    matched = "bucket = 'match' AND __cin IS NOT NULL AND __din IS NOT NULL"
    return (
        # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL is the run's own and the table name the tool's
        f"{ctes},\n"
        f"__match AS (\n  SELECT {joined_key} AS __key FROM joined\n"
        f"  WHERE {matched}\n),\n"
        f"__other AS (\n  SELECT {joined_key} AS __key FROM joined\n"
        f"  WHERE NOT ({matched})\n),\n"
        f"__saved AS (\n  SELECT {dash_key} AS __key FROM {saved_table}\n"
        "  WHERE bucket != 'cube_only'\n  UNION DISTINCT\n"
        f"  SELECT {cube_key} AS __key FROM {saved_table}\n"
        "  WHERE bucket != 'dashboard_only'\n),\n"
        "__matched AS (\n  SELECT __key FROM __match WHERE __key IS NOT NULL\n"
        "  EXCEPT DISTINCT SELECT __key FROM __other\n"
        "  EXCEPT DISTINCT SELECT __key FROM __saved\n)"
    )


def dashboard_side_sql(
    cfg: ViewConfig,
    comparison: Comparison,
    cuts: list[dict[str, Any]],
    build: Build,
    wh: Warehouse,
    *,
    keep: bool,
) -> str:
    """The dashboard's cells per cut, from its sheet query as of the build start.

    Args:
        cfg: The view's config.
        comparison: A comparison with `rows`.
        cuts: The cuts to compute, each tagged `__cut` with its label.
        build: The run's moment; the dashboard is read as of its start.
        wh: The warehouse, for view history.
        keep: True reads only the matched rows: the rows the reconcile reads
            whose key `__matched` holds, so the caller prefixes `matched_ctes`.
            False reads every row through the same rewrite, for the self-check
            that it reproduces the run's cells.

    Returns:
        A `UNION ALL` of one SELECT per cut.

    Raises:
        pipeline.Refusal: `keep` is True and the comparison has no `rows`, or
            the SQL cannot be read as of the build start.
    """
    if keep:
        grain = _rows(comparison).grain
        dates = pipeline.date_cubes(cfg)
        key = key_sql([p.dashboard for p in grain], [p.cube in dates for p in grain])
        rows = (
            # trunk-ignore(bandit/B608): identifiers are validated in config.py
            f"SELECT * FROM ({pipeline.dashboard_scoped_rows_sql(cfg, comparison)}) "
            f"WHERE {key} IN (SELECT __key FROM __matched)"
        )
    else:
        rows = (
            # trunk-ignore(bandit/B608): identifiers are validated in config.py
            f"SELECT * FROM (SELECT * FROM {pipeline.dashboard_ref(comparison)}) "
            "WHERE TRUE"
        )
    parts = []
    for cut in cuts:
        sql = pipeline.sheet_query(cfg, comparison, cut, rows=rows)
        at = pipeline.checked_as_of(sql, build.start, wh)
        label = pipeline.lit(pipeline.cut_label(cut))
        # trunk-ignore(bandit/B608): the label is literal-escaped and the SQL the tool's own
        parts.append(f"SELECT {label} AS __cut, * FROM (\n{at.sql}\n)")
    return "\nUNION ALL\n".join(parts)


def cube_read_tables(cfg: ViewConfig, compiled_sql: str) -> list[str]:
    """The facts Cube's cell SQL reads: `cfg.fact` and each of `cfg.also_facts`
    the SQL names.

    Args:
        cfg: The view's config.
        compiled_sql: Cube's compiled SQL for a cell query.

    Returns:
        `dataset.table` names as the config spells them, `cfg.fact` first.
    """
    found = {
        f"{ds}.{name}".lower()
        for ds, name in cube_client._FACT_REF.findall(compiled_sql)
    }
    return [cfg.fact, *(f for f in cfg.also_facts if f.lower() in found)]


def fact_grain(
    compiled_rows_sql: str, view: str, grain: list[str]
) -> tuple[str, list[str]]:
    """The table Cube's row SQL reads the grain from, and its column per member.

    Only a plain column of a table in the outermost SELECT's `FROM` or `JOIN`
    counts: the Cube side filters that table by those columns.

    Args:
        compiled_rows_sql: Cube's compiled SQL for the comparison's rows.
        view: The Cube view, whose members Cube selects as `<view>__<member>`.
        grain: The grain's Cube members, the student first.

    Returns:
        The `dataset.table` and, per member in order, its column there.

    Raises:
        NotCompared: The SQL cannot be parsed, a member is not a plain column
            of a table, or the members sit on more than one table.
    """
    try:
        tree = sqlglot.parse_one(compiled_rows_sql, read="bigquery")
    except SqlglotError as exc:
        raise NotCompared("Cube's SQL could not be parsed") from exc
    sources: dict[str, exp.Expr] = {}
    projections: dict[str, exp.Expr] = {}
    if isinstance(tree, exp.Select):
        start = tree.args.get("from_")
        reads = [start.this] if start else []
        reads += [j.this for j in tree.args.get("joins") or []]
        sources = {s.alias_or_name: s for s in reads}
        projections = {p.alias_or_name: p.unalias() for p in tree.expressions}
    tables: set[str] = set()
    columns: list[str] = []
    for m in grain:
        column = projections.get(f"{view}__{m}")
        source = sources.get(column.table) if isinstance(column, exp.Column) else None
        # A subquery, a table with no dataset or a missing member is no fact.
        if (
            not isinstance(column, exp.Column)
            or not isinstance(source, exp.Table)
            or not source.db
        ):
            raise NotCompared(f"grain column {m} is an expression, not a fact column")
        tables.add(f"{source.db}.{source.name}")
        columns.append(column.name)
    if len(tables) > 1:
        raise NotCompared("the grain columns sit on more than one table")
    return tables.pop(), columns


def filtered_tables(
    read: list[str], columns: list[str], columns_of: Callable[[str], set[str]]
) -> list[str]:
    """The tables Cube reads that carry every grain column.

    A table without them, such as a goals table at school and grade grain, is
    a lookup the matched rows cannot filter, so it is read as is.

    Args:
        read: The `dataset.table` names Cube's SQL reads (`cube_read_tables`).
        columns: The grain's columns on the fact (`fact_grain`).
        columns_of: A table's column names, by its `dataset.table`.

    Returns:
        The tables of `read`, in order, that carry every grain column.

    Raises:
        NotCompared: No table of `read` carries them.
    """
    # BigQuery column names ignore case.
    need = {c.lower() for c in columns}
    kept = [t for t in read if need <= {c.lower() for c in columns_of(t)}]
    if not kept:
        raise NotCompared("no table Cube reads carries the grain columns")
    return kept


def rewrite_cube_sql(
    sql: str, tables: list[str], columns: list[str], dates: list[bool], *, keep: bool
) -> str:
    """Read each table of `tables` in Cube's pinned SQL through a filter.

    Every reference keeps its own moment and alias, so the SQL around it reads
    the filtered rows under the same name.

    Args:
        sql: Cube's SQL as `timetravel.as_of` and `repin` leave it.
        tables: The `dataset.table` names to filter (`filtered_tables`).
        columns: The grain's columns on each of them.
        dates: Per column, whether it is a date grain.
        keep: True keeps only the rows whose key `__matched` holds, so the
            caller prefixes `matched_ctes`. False keeps every row, for the
            self-check that the rewrite reproduces the run's cells.

    Returns:
        The rewritten SQL.

    Raises:
        NotCompared: A table is not read, is read with no alias, or is read in
            a form the rewrite cannot place.
    """
    predicate = (
        # trunk-ignore(bandit/B608): the grain columns are Cube's own fact columns
        f"{key_sql(columns, dates)} IN (SELECT __key FROM __matched)"
        if keep
        else "TRUE"
    )
    for t in pipeline.unique(tables):
        ref = re.escape(f"`{PROJECT}.{t}`")
        # `as_of` keeps a dbt reference's alias as written, `AS` or not; a
        # clause keyword such as FOR is never an alias.
        pattern = re.compile(
            ref
            + r"(?P<alias>\s+AS\s+`?\w+`?|\s+(?!(?:"
            + _NOT_ALIAS
            + r")\b)`?\w+`?)?\s+FOR SYSTEM_TIME AS OF TIMESTAMP '(?P<at>[^']+)'",
            re.IGNORECASE,
        )
        found = list(pattern.finditer(sql))
        reads = len(re.findall(ref, sql, re.IGNORECASE))
        if not reads:
            raise NotCompared(f"Cube's SQL does not read {t}")
        if reads != len(found):
            # A reference left unwrapped would read every row on one side only.
            raise NotCompared(
                f"Cube's SQL reads {t} in a form the rewrite does not know"
            )
        if any(m["alias"] is None for m in found):
            # Cube's columns name the table, which a subquery would hide.
            raise NotCompared(f"Cube's SQL reads {t} with no alias")
        sql = pattern.sub(
            lambda m, t=t: (
                # trunk-ignore(bandit/B608): the table is the config's own and the timestamp Cube's pinned literal
                f"(SELECT * FROM `{PROJECT}.{t}` FOR SYSTEM_TIME AS OF TIMESTAMP "
                f"'{m['at']}' WHERE {predicate}){m['alias']}"
            ),
            sql,
        )
    return sql


def cube_side_sql(
    cfg: ViewConfig,
    comparison: Comparison,
    cuts: list[dict[str, Any]],
    build: Build,
    *,
    ex: pipeline.Expand,
    sides: pipeline.RowSides,
    tables: list[str],
    columns: list[str],
    keep: bool,
) -> str:
    """Cube's cells per cut, from its compiled cell SQL as of the build end.

    A table the dashboard's rows also read is read at the build start, as the
    run's Cube rows read it, so one query reads each table at one moment.

    Args:
        cfg: The view's config.
        comparison: A comparison with `rows`.
        cuts: The cuts to compute, each tagged `__cut` with its label.
        build: The run's moment.
        ex: Compiles and expands the comparison's Cube SQL.
        sides: The row SQL the run reconciled for it.
        tables: The tables to filter (`filtered_tables`).
        columns: The grain's columns on them (`fact_grain`).
        keep: True reads only the matched rows, so the caller prefixes
            `matched_ctes`; False reads every row, for the self-check.

    Returns:
        A `UNION ALL` of one SELECT per cut, Cube's members by name and the
        measure as `value`.

    Raises:
        pipeline.Refusal: The comparison has no `rows`, or Cube's SQL cannot
            be read as of the build end (`pipeline.checked_as_of`).
        CubeRefusal: Cube's compiled SQL fails `refuse_unless_safe`.
        CubeError: Cube answered the compile with an HTTP error.
        ViewHistoryError: A view's definition at the moment is not on record.
        GoogleAPIError: A lookup the expansion makes, such as a view's
            history, failed in BigQuery.
        CostCapError: That lookup would pass a cap.
        NotCompared: Cube's SQL cannot be rewritten (`rewrite_cube_sql`).
    """
    dates = pipeline.date_cubes(cfg)
    grain_dates = [p.cube in dates for p in _rows(comparison).grain]
    dims = [d.cube for d in comparison.dims]
    parts = []
    for cut in cuts:
        query = pipeline.cell_query(cfg.view, comparison, cut)
        at = ex.at(ex.cube_sql(query), build.end)
        shared = sorted(at.tables & sides.dashboard.tables)
        sql = repin(at.sql, shared, build.end, build.start)
        sql = rewrite_cube_sql(sql, tables, columns, grain_dates, keep=keep)
        cells = pipeline.wrap_cube(sql, cfg.view, dims, dates, comparison.measure)
        label = pipeline.lit(pipeline.cut_label(cut))
        # trunk-ignore(bandit/B608): the label is literal-escaped and the SQL the tool's own
        parts.append(f"SELECT {label} AS __cut, * FROM (\n{cells}\n)")
    return "\nUNION ALL\n".join(parts)


# --- the check in `sort` --------------------------------------------------------


@dataclass
class Job:
    """One comparison's formula check, planned and ready to price and run.

    `sql` holds the 4 queries by name: `dashboard` and `cube` read matched
    rows only, `dashboard_self` and `cube_self` every row (the self-check).
    """

    comparison: str
    fingerprint: str
    cells: list[dict]
    sql: dict[str, str]


def checkable_cells(run: RunResult, comparison: Comparison) -> list[dict]:
    """The comparison's differing cells the check can recompute.

    Each is a `kind: cells` entry of `run.diff_cells` that coverage places
    (`coverage.placed`) with at least 1 group, open or closed by a decision.
    A cell with no group in it is already a formula difference.
    """
    groups = [*run.applied.open, *(g for _, g in run.applied.quiet)]
    return [
        c
        for c in run.diff_cells
        if c["comparison"] == comparison.id
        and c.get("kind", "cells") == "cells"
        and coverage.placed(c, groups, comparison)
    ]


def not_compared(
    comparison: str, fingerprint: str, cells: list[dict], why: str
) -> Check:
    """A check that recomputed nothing: every cell left to coverage for `why`."""
    return Check(
        comparison,
        fingerprint,
        not_compared={why: [(c["cut"], c["key"]) for c in cells]},
    )


def _job_sql(
    cfg: ViewConfig,
    comparison: Comparison,
    cells: list[dict],
    build: Build,
    *,
    wh: Warehouse,
    cube: Cube,
    schools: set[str],
    sides: pipeline.RowSides,
    table: str,
) -> dict[str, str]:
    """The check's 4 queries over the cuts `cells` sit in, as `Job.sql` holds them."""
    held = {c["cut"] for c in cells}
    cuts = [
        c for c in pipeline.comparison_cuts(comparison) if pipeline.cut_label(c) in held
    ]
    ctes = matched_ctes(cfg, comparison, sides, table)
    ex = pipeline.Expand(cfg, cube, schools, wh)
    grain = [p.cube for p in _rows(comparison).grain]
    _, columns = fact_grain(
        ex.cube_sql(pipeline.row_query(cfg.view, comparison), rows=True),
        cfg.view,
        grain,
    )
    compiled = "\n".join(
        ex.cube_sql(pipeline.cell_query(cfg.view, comparison, cut)) for cut in cuts
    )
    tables = filtered_tables(
        cube_read_tables(cfg, compiled),
        columns,
        lambda t: wh.columns(*t.split(".", 1)),
    )

    def dash(keep: bool) -> str:
        return dashboard_side_sql(cfg, comparison, cuts, build, wh, keep=keep)

    def cubes(keep: bool) -> str:
        return cube_side_sql(
            cfg, comparison, cuts, build,
            ex=ex, sides=sides, tables=tables, columns=columns, keep=keep,
        )  # fmt: skip

    def matched(body: str) -> str:
        # trunk-ignore(bandit/B608): both parts are the tool's own SQL
        return f"{ctes}\nSELECT * FROM (\n{body}\n)"

    return {
        "dashboard": matched(dash(True)),
        "cube": matched(cubes(True)),
        "dashboard_self": dash(False),
        "cube_self": cubes(False),
    }


def plan(
    cfg: ViewConfig,
    run: RunResult,
    comparison: Comparison,
    *,
    fingerprint: str,
    wh: Warehouse,
    cube: Cube,
    prepared: trace.Prepared,
) -> Job | Check | None:
    """Build the comparison's formula check, or why it cannot be built.

    Reads the run's row SQL (`prepared.row_sides`), its saved rows
    (`explain.require_saved`), Cube's compiled SQL and the fact's columns;
    no priced query runs. Never raises: every failure is a check whose cells
    are all left to coverage under one reason. The run's SQL no longer
    building as it did, or the moment no longer readable, is `SQL_MOVED`;
    the saved rows gone or of another run, `SAVED_GONE`; Cube's refusal or
    error, `CUBE_REFUSED`; a Cube side the rewrite cannot place, its own
    reason (`NotCompared`); a BigQuery error, its job and reason code; a cap,
    `CAPPED`; anything else, `UNBUILT`, with the error printed.

    BigQuery reads a table at 1 moment per query, so a sheet query whose
    template joins a table the Cube row SQL inside `matched_ctes` reads at
    the other moment is refused when it runs: that lands as a BigQuery
    error in `run_job`, never a crash.

    Args:
        cfg: The view's config.
        run: The run the check reads, as `sort` composed it.
        comparison: A confirmed comparison of the run.
        fingerprint: Its latest result's `checkpoint_fingerprint`, which the
            check is kept under.
        wh: The warehouse, for view history, saved labels and columns.
        cube: Cube, for the compiled SQL.
        prepared: What the triage fetched once; its row SQL is reused.

    Returns:
        None when no cell can be checked (`checkable_cells`); a `Job` holding
        the 4 queries; else the fallback check.
    """
    cells = checkable_cells(run, comparison)
    if not cells:
        return None
    # What a `Refusal` means depends on the step that raised it.
    refused = SQL_MOVED
    try:
        sides = prepared.row_sides(cfg, comparison, run, wh, cube)
        refused = SAVED_GONE
        table = explain.require_saved(wh, cfg, run, comparison)
        refused = SQL_MOVED
        sql = _job_sql(
            cfg, comparison, cells, run.moment_of(comparison.id),
            wh=wh, cube=cube, schools=prepared.schools or set(), sides=sides,
            table=table,
        )  # fmt: skip
    except NotCompared as exc:
        why = str(exc)
    except pipeline.Refusal:
        why = refused
    except (CubeRefusal, CubeError):
        why = CUBE_REFUSED
    except ViewHistoryError:
        why = SQL_MOVED
    except GoogleAPIError as exc:
        why = bigquery_refused(exc)
    except CostCapError:
        why = CAPPED
    except Exception as exc:  # noqa: BLE001 - the check never stops `sort`
        print(f"Formula check of {comparison.id} not built: {exc!r}")
        why = UNBUILT
    else:
        return Job(comparison.id, fingerprint, cells, sql)
    return not_compared(comparison.id, fingerprint, cells, why)


def run_job(job: Job, comparison: Comparison, wh: Warehouse) -> Check:
    """Run a planned check's 4 queries and decide its cells (`verdicts`).

    Call inside `wh.budget`, after its dry runs are priced. Never raises: a
    BigQuery error leaves every cell to coverage under its job and reason
    code, a cap under `CAPPED`, and rows that do not carry the comparison's
    dims under `REWRITE_DIFFERS`.
    """
    try:
        got = {k: wh.rows(sql, timeout_s=trace.TIMEOUT_S) for k, sql in job.sql.items()}
    except GoogleAPIError as exc:
        return not_compared(job.comparison, job.fingerprint, job.cells,
                            bigquery_refused(exc))  # fmt: skip
    except CostCapError:
        return not_compared(job.comparison, job.fingerprint, job.cells, CAPPED)
    try:
        return verdicts(
            comparison, job.fingerprint, job.cells,
            got["dashboard"], got["cube"], got["dashboard_self"], got["cube_self"],
        )  # fmt: skip
    except (KeyError, TypeError, ValueError):
        return not_compared(job.comparison, job.fingerprint, job.cells,
                            REWRITE_DIFFERS)  # fmt: skip


def ran(check: Check) -> bool:
    """Whether the check ran its queries, so it can be kept for the next sort."""
    return all(why in _RAN for why in check.not_compared)


def label(items: list[dict], checks: dict[str, Check]) -> dict[str, dict[str, int]]:
    """Disclose, on each comparison's cell set, the cells the check left to coverage.

    Prepends one line per reason to the `<id>:cells` item's evidence, its count
    exact locally and masked (`mask`) in `evidence_posted`. Names no cell.

    Returns:
        Per comparison with any, each reason's cell count, for `triage.json`.
    """
    by_id = {i["id"]: i for i in items}
    out: dict[str, dict[str, int]] = {}
    for cid, check in checks.items():
        counts = {why: len(c) for why, c in check.not_compared.items() if c}
        if not counts:
            continue
        out[cid] = counts
        item = by_id.get(f"{cid}:cells")
        if item is None:
            continue

        def line(why: str, n: str) -> str:
            return f"{NOT_COMPARED}: {why} ({n} cells closed by coverage only)"

        evidence = item.get("evidence") or []
        posted = item.get("evidence_posted") or evidence
        item["evidence"] = [*(line(w, str(n)) for w, n in counts.items()), *evidence]
        item["evidence_posted"] = [
            *(line(w, mask(n)) for w, n in counts.items()),
            *posted,
        ]
    return out
