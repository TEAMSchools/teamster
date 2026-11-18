"""Recompute a comparison's differing cells on the rows both sides matched.

A cell that still differs once both sides read only matched rows differs by
its formula, not by its rows. Matched rows are the rows the reconcile matched,
minus every saved unmatched key: the grain keys the run's own `joined` files
`match` with both sides present, less any key it also files otherwise (an
unmatched duplicate, a row a dashboard filter drops) and any key the run saved
as unmatched. Rows the reconcile never saw, such as out-of-scope or non-latest
daily rows, are never matched, so they can never read as a formula difference.
The module is pure: it builds SQL and runs nothing.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from . import cube_client, pipeline, reconcile
from .bq import Warehouse
from .config import Comparison, RowSpec, ViewConfig
from .moment import Build
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


class NotCompared(Exception):
    """The formula check cannot run; the text is one of this module's reasons."""


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
        pipeline.Refusal: The comparison has no `rows`.
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
