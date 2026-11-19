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
from .config import Comparison, ViewConfig
from .cube_client import Cube, CubeError, CubeRefusal
from .moment import Build
from .report import RunResult, mask
from .timetravel import _NOT_ALIAS, PROJECT, closing_paren, repin

# A cell the check could not recompute closes by coverage under this label,
# followed by one of the reasons below.
NOT_COMPARED = "formulas not compared"
REWRITE_DIFFERS = "the rewrite does not reproduce the run's cells"
NO_ROWS = "no rows both sides hold"
FANS_OUT = "a join on the grain's path repeats the fact's rows"
SAVED_GONE = "its saved rows are gone or of another run; compare it again"
SQL_MOVED = "its SQL changed since the run; compare it again"
CUBE_REFUSED = "Cube refused its SQL; sort again"
NOT_COMPOSED = "the run is not composed from the latest results; compare it again"
OUTSIDE = "not run: outside --comparison; sort it"
CAPPED = "a cap stopped it; sort again with a higher --max-usd"
# An error no reason above names, from code that builds the check's SQL.
UNBUILT = "its SQL could not be built (see the terminal); sort again"
# An error no reason above names, from pricing or running the check's queries,
# such as expired credentials.
RUN_FAILED = "its queries failed (see the terminal); sort again"
# The reasons a check that ran its queries can give; any other is a failure.
_RAN = (REWRITE_DIFFERS, NO_ROWS, FANS_OUT)
# The check's code version, kept with each check. Bump it whenever the check's
# SQL or its verdicts change. `sort` reuses a kept check of the latest result
# only while its version is this one, whatever cells it left uncompared, so
# nothing is spent again until the comparison is compared again; a bump runs
# every kept check again, so a fix to its formula or coverage verdicts takes
# effect.
CHECK_VERSION = 2


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
    cut, dims and both values: local only, never posted. `version` is the
    `CHECK_VERSION` of the code that made it.
    """

    comparison: str
    fingerprint: str
    formula: list[CellRef] = field(default_factory=list)
    coverage: list[CellRef] = field(default_factory=list)
    not_compared: dict[str, list[CellRef]] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)
    version: int = CHECK_VERSION

    def to_json(self) -> dict:
        """The check as JSON data, cells as `[cut, key]` pairs."""
        return {
            "comparison": self.comparison,
            "fingerprint": self.fingerprint,
            "version": self.version,
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
        """The check `to_json` wrote, its cells as tuples again. A check kept
        before checks carried a version reads as version 0."""

        def refs(cells: list) -> list[CellRef]:
            return [(cut, key) for cut, key in cells]

        return cls(
            comparison=data["comparison"],
            fingerprint=data["fingerprint"],
            formula=refs(data["formula"]),
            coverage=refs(data["coverage"]),
            not_compared={why: refs(c) for why, c in data["not_compared"].items()},
            lines=list(data["lines"]),
            version=int(data.get("version", 0)),
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


def _keyed(keys: list[str]) -> str:
    """One row's key from its grain keys; NULL when the first, the student, is."""
    fields = ", ".join(f"{k} AS k{i}" for i, k in enumerate(keys))
    return f"IF({keys[0]} IS NULL, NULL, TO_JSON_STRING(STRUCT({fields})))"


def key_sql(
    columns: list[str], dates: list[bool], tables: list[str] | None = None
) -> str:
    """The key of one row from its grain columns, keyed as the reconcile keys
    them.

    Beyond the reconcile's keys, a date column is first cast to DATE here, so
    a TIMESTAMP and the DATE of the same day key alike. Each column is quoted,
    so a column named by a reserved word, such as `order`, still reads.

    Args:
        columns: The row's grain columns by plain name, the student first.
        dates: Per column, whether it is a date grain.
        tables: Per column, the alias of the table it is read from, when the
            columns sit on more than one.

    Returns:
        A string expression; NULL when the first column's key is NULL.
    """
    on = tables or [None] * len(columns)
    named = [
        f"`{t}`.`{c}`" if t else f"`{c}`" for c, t in zip(columns, on, strict=True)
    ]
    read = [
        f"CAST({c} AS DATE)" if is_date else c
        for c, is_date in zip(named, dates, strict=True)
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
    n = len(pipeline.rows_of(comparison).grain)
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


ROWS_BYPASSED = "its sheet_query_sql does not read every row through {rows}"


def _reads_only_rows(comparison: Comparison) -> None:
    """Refuse a `sheet_query_sql` that reads a dashboard row other than
    through `{rows}`.

    The matched-rows side swaps `{rows}` for the matched rows only; a
    template that skips `{rows}`, or names the dashboard view beside it,
    would read every row there while Cube's side reads matched rows, and the
    self-check would not see it.

    Raises:
        NotCompared: The template has no `{rows}`, or names the view.
    """
    template = comparison.sheet_query_sql
    if not template:
        return
    marker = "__formula_rows__"
    text = template.format(rows=marker, where="TRUE", dims="").replace("`", "")
    view = re.escape(comparison.dashboard_view or "")
    if marker not in text or (view and re.search(rf"\b{view}\b", text, re.IGNORECASE)):
        raise NotCompared(ROWS_BYPASSED)


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
        NotCompared: `keep` is True and the comparison's `sheet_query_sql`
            reads a row other than through `{rows}` (`_reads_only_rows`).
    """
    if keep:
        grain = pipeline.rows_of(comparison).grain
        dates = pipeline.date_cubes(cfg)
        key = key_sql([p.dashboard for p in grain], [p.cube in dates for p in grain])
        rows = (
            # trunk-ignore(bandit/B608): identifiers are validated in config.py
            f"SELECT * FROM ({pipeline.dashboard_scoped_rows_sql(cfg, comparison)}) "
            f"WHERE {key} IN (SELECT __key FROM __matched)"
        )
        _reads_only_rows(comparison)
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


@dataclass(frozen=True)
class Hop:
    """One of Cube's joins on the grain's path: `kind` (`LEFT JOIN` or
    `INNER JOIN`) to `table` (`dataset.table` as Cube's SQL spells it) as
    `alias`, `on` an AND of column equalities with 1 table before it."""

    alias: str
    table: str
    kind: str
    on: str


@dataclass(frozen=True)
class Grain:
    """Where Cube's row SQL reads a comparison's grain.

    `keys` holds each member's (alias, column), in grain order. With no
    `hops`, every column sits on `table`, read as `alias`, which is a fact.
    Otherwise `table` is the view's fact, read as `alias`, and `hops` are
    Cube's joins from it to every other alias `keys` names, in Cube's order.
    """

    table: str
    alias: str
    keys: tuple[tuple[str, str], ...]
    hops: tuple[Hop, ...] = ()

    @property
    def columns(self) -> list[str]:
        """Each member's column, in grain order."""
        return [column for _, column in self.keys]


def _path_join(alias: str, join: exp.Join) -> tuple[str, Hop]:
    """The table before `alias` on the grain's path, and the hop to `alias`.

    Raises:
        NotCompared: The join is no LEFT or INNER join of a table with a
            dataset, on an AND of column equalities between `alias` and 1
            table before it.
    """
    where = f"the join to {alias} on the grain's path"
    kinds = {("LEFT", ""): "LEFT JOIN", ("LEFT", "OUTER"): "LEFT JOIN",
             ("", ""): "INNER JOIN", ("", "INNER"): "INNER JOIN"}  # fmt: skip
    kind = kinds.get((join.side.upper(), join.kind.upper()))
    if kind is None or join.method:
        raise NotCompared(f"{where} is not a LEFT or INNER join")
    target = join.this
    if not isinstance(target, exp.Table) or not target.db:
        raise NotCompared(f"{where} reads a subquery or a table with no dataset")
    on = join.args.get("on")
    if on is None or join.args.get("using"):
        raise NotCompared(f"{where} is not on an equality of columns")
    on = on.unnest()
    parts = list(on.flatten()) if isinstance(on, exp.And) else [on]
    pairs: list[tuple[exp.Column, exp.Column]] = []
    for part in parts:
        part = part.unnest()
        if not (
            isinstance(part, exp.EQ)
            and isinstance(part.left, exp.Column)
            and isinstance(part.right, exp.Column)
            and part.left.table
            and part.right.table
        ):
            raise NotCompared(f"{where} is not on an equality of columns")
        pairs.append((part.left, part.right))
    before = {c.table for pair in pairs for c in pair} - {alias}
    if len(before) != 1 or any(
        {a.table, b.table} != {alias, *before} for a, b in pairs
    ):
        raise NotCompared(
            f"{where} does not compare it with exactly one table before it"
        )
    text = " AND ".join(
        f"`{a.table}`.`{a.name}` = `{b.table}`.`{b.name}`" for a, b in pairs
    )
    return before.pop(), Hop(alias, f"{target.db}.{target.name}", kind, text)


def fact_grain(
    compiled_rows_sql: str, view: str, grain: list[str], facts: list[str]
) -> Grain:
    """Where Cube's row SQL reads the grain: its column per member, and the
    joins that carry each one to the fact.

    Only a plain column of a table in the outermost SELECT's `FROM` or `JOIN`
    counts. When every member sits on one table of `facts`, that table is the
    grain's and the Cube side filters it as is. Otherwise each member's table
    must be reached from the view's fact through Cube's own joins, each a
    LEFT or INNER join on column equalities with the table before it: the
    Cube side then keys the fact's rows through those joins, never by a
    column of another table that only shares a name.

    Args:
        compiled_rows_sql: Cube's compiled SQL for the comparison's rows.
        view: The Cube view, whose members Cube selects as `<view>__<member>`.
        grain: The grain's Cube members, the student first.
        facts: The view's fact, then its `also_facts`, as `dataset.table`.

    Returns:
        The grain's `Grain`.

    Raises:
        NotCompared: The SQL cannot be parsed or is no single SELECT; a
            member is missing from it or is not a plain column of a table with
            a dataset; or the grain sits off one fact and the fact is not read
            once, or a member's table is not reached from it that way, or
            the path joins one of the `also_facts`.
    """
    try:
        tree = sqlglot.parse_one(compiled_rows_sql, read="bigquery")
    except SqlglotError as exc:
        raise NotCompared("Cube's SQL could not be parsed") from exc
    if not isinstance(tree, exp.Select):
        raise NotCompared("Cube's row SQL is not a single SELECT")
    start = tree.args.get("from_")
    reads = [start.this] if start else []
    joins = tree.args.get("joins") or []
    reads += [j.this for j in joins]
    sources = {s.alias_or_name: s for s in reads}
    projections = {p.alias_or_name: p.unalias() for p in tree.expressions}
    keys: list[tuple[str, str]] = []
    for m in grain:
        column = projections.get(f"{view}__{m}")
        if column is None:
            raise NotCompared(f"grain member {m} is not in Cube's row SQL")
        if not isinstance(column, exp.Column):
            raise NotCompared(f"grain column {m} is an expression, not a fact column")
        source = sources.get(column.table)
        if source is None:
            raise NotCompared(f"grain column {m} names no table of the outer FROM")
        if not isinstance(source, exp.Table):
            raise NotCompared(f"grain column {m} is read from a subquery, not a fact")
        if not source.db:
            # A CTE reads as a table with no dataset too.
            raise NotCompared(
                f"grain column {m} sits on a CTE or a table with no dataset"
            )
        keys.append((column.table, column.name))

    def table_of(alias: str) -> str:
        source = sources[alias]
        return f"{source.db}.{source.name}"

    on = {alias for alias, _ in keys}
    if len(on) == 1 and table_of(next(iter(on))).lower() in {f.lower() for f in facts}:
        alias = next(iter(on))
        return Grain(table_of(alias), alias, tuple(keys))
    fact = facts[0]
    starts = [
        s.alias_or_name
        for s in reads
        if isinstance(s, exp.Table) and f"{s.db}.{s.name}".lower() == fact.lower()
    ]
    if len(sources) != len(reads):
        # One alias per table read, so each join names the table it means.
        raise NotCompared("Cube's row SQL reads 2 tables under one alias")
    if len(starts) != 1:
        raise NotCompared(
            "the grain sits off the fact, and Cube's row SQL does not read the "
            f"fact {fact}" + (" once" if starts else "")
        )
    root = starts[0]
    by_alias = {j.this.alias_or_name: j for j in joins}
    hops: dict[str, Hop] = {}
    for m, (alias, _) in zip(grain, keys, strict=True):
        at, seen = alias, set()
        while at != root and at not in hops:
            if at in seen or at not in by_alias:
                raise NotCompared(
                    f"grain member {m} sits on {alias}, which no chain of joins "
                    "from the fact reaches"
                )
            seen.add(at)
            before, hops[at] = _path_join(at, by_alias[at])
            if hops[at].table.lower() in {f.lower() for f in facts[1:]}:
                # The rewrite filters the fact alone; another fact on the
                # path would be read whole.
                raise NotCompared(
                    f"the join to {at} on the grain's path reads "
                    f"{hops[at].table}, one of the view's also_facts"
                )
            at = before
    return Grain(
        table_of(root),
        root,
        tuple(keys),
        tuple(hops[a] for a in by_alias if a in hops),
    )


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


# The close of `as_of`'s wrapper for a table read through a PIVOT, its alias
# if any, and the PIVOT.
_PIVOT_AFTER = re.compile(
    r"\)(?:\s+AS\s+`?\w+`?|\s+(?!(?:un)?pivot\b)`?\w+`?)?\s*(?:un)?pivot\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Path:
    """A grain off the fact (`Grain` with `hops`) and its hops as SQL: each
    join's table read as the run's Cube rows read it, moment included, and
    Cube's own ON clause (`path_joins`)."""

    grain: Grain
    joins: str


def _pinned_read(pinned_sql: str, hop: Hop) -> str:
    """How `pinned_sql` reads `hop`'s table: the pinned table and its alias,
    or, for a view `as_of` inlined, the view's SQL in parentheses and its
    alias.

    Raises:
        NotCompared: It is read in neither form exactly once, such as an
            external table read live.
    """
    ds, name = hop.table.split(".", 1)
    alias = re.escape(f"`{hop.alias}`")
    table = re.compile(
        re.escape(f"`{PROJECT}.{ds}.{name}`")
        + rf"\s+AS\s+{alias}\s+FOR SYSTEM_TIME AS OF TIMESTAMP '[^']+'",
        re.IGNORECASE,
    )
    found = [m[0] for m in table.finditer(pinned_sql)]
    for join in re.finditer(r"\bJOIN\s+\(", pinned_sql, re.IGNORECASE):
        close = closing_paren(pinned_sql, join.end() - 1)
        named = re.compile(rf"\s+AS\s+{alias}").match(pinned_sql, close + 1)
        if named:
            found.append(pinned_sql[join.end() - 1 : named.end()])
    if len(found) != 1:
        raise NotCompared(
            f"Cube's SQL reads {hop.table} in a form the rewrite does not know"
        )
    return found[0]


def path_joins(grain: Grain, pinned_rows_sql: str, *, left: bool = False) -> str:
    """The joins of `grain`'s path as SQL, each table read as `pinned_rows_sql`
    reads it.

    Args:
        grain: A `Grain` with `hops` (`fact_grain`).
        pinned_rows_sql: Cube's row SQL as `as_of` and `repin` leave it for the
            run's Cube rows, so each table keeps that moment.
        left: Write every hop as a LEFT JOIN, whatever Cube's kind.

    Returns:
        One `<kind> <table> ON <on>` per hop, in Cube's order.

    Raises:
        NotCompared: A hop's table is read in a form `_pinned_read` does not
            know.
    """
    return "\n".join(
        f"{'LEFT JOIN' if left else hop.kind} "
        f"{_pinned_read(pinned_rows_sql, hop)} ON {hop.on}"
        for hop in grain.hops
    )


def _read_pattern(table: str) -> re.Pattern[str]:
    """A read of `table` (`dataset.table`) in pinned SQL: the reference, its
    alias if any, and its moment."""
    ref = re.escape(f"`{PROJECT}.{table}`")
    # `as_of` keeps a dbt reference's alias as written, `AS` or not; a clause
    # keyword such as FOR is never an alias. The table is matched ignoring
    # case, as `cube_read_tables` finds it, but written back as Cube's SQL
    # spells it: BigQuery's dataset and table names keep case.
    return re.compile(
        f"(?P<ref>{ref})"
        + r"(?P<alias>\s+AS\s+`?\w+`?|\s+(?!(?:"
        + _NOT_ALIAS
        + r")\b)`?\w+`?)?\s+FOR SYSTEM_TIME AS OF TIMESTAMP '(?P<at>[^']+)'",
        re.IGNORECASE,
    )


def fanout_sql(pinned_cells: list[str], grain: Grain, pinned_rows_sql: str) -> str:
    """Per moment the cells read the fact at, its row count alone and through
    the path's joins.

    Every hop is a LEFT JOIN here, so each fact row comes out at least once
    and the counts are equal only when no join repeats a row; Cube's own
    INNER join could otherwise drop one row and hide another's repeat. The
    self-check alone misses a repeat a measure such as a distinct count does
    not move, and a repeated row can carry an unmatched key into the matched
    rows.

    Args:
        pinned_cells: Cube's cell SQL per cut, as `cube_side_sql` pins it.
        grain: A `Grain` with `hops`.
        pinned_rows_sql: The run's Cube row SQL (`sides.cube_rows_sql`).

    Returns:
        One row per moment, `__joined` and `__fact`.

    Raises:
        NotCompared: The cells do not read the fact, or a hop's table is read
            in a form `_pinned_read` does not know.
    """
    joins = path_joins(grain, pinned_rows_sql, left=True)
    pattern = _read_pattern(grain.table)
    fact = f"`{grain.alias}`"
    reads = pipeline.unique(
        f"{m['ref']} AS {fact} FOR SYSTEM_TIME AS OF TIMESTAMP '{m['at']}'"
        for sql in pinned_cells
        for m in pattern.finditer(sql)
    )
    if not reads:
        raise NotCompared(f"Cube's SQL does not read {grain.table}")
    return "\nUNION ALL\n".join(
        # trunk-ignore(bandit/B608): the tables, joins and timestamps are Cube's own, as the run read them
        f"SELECT (SELECT COUNT(*) FROM {r}\n{joins}) AS __joined, "
        f"(SELECT COUNT(*) FROM {r}) AS __fact"
        for r in reads
    )


def rewrite_cube_sql(
    sql: str,
    tables: list[str],
    columns: list[str],
    dates: list[bool],
    *,
    keep: bool,
    path: Path | None = None,
) -> str:
    """Read each table of `tables` in Cube's pinned SQL through a filter.

    Every reference keeps its own moment and alias, so the SQL around it reads
    the filtered rows under the same name. With a `path`, each reference
    reads the fact's own columns from the fact joined, through Cube's joins,
    to every table the grain sits on, and is filtered by the grain's key
    over those tables; a join that repeats a fact row repeats it in the
    self-check too, and `fanout_sql` catches the repeat a measure hides.

    Args:
        sql: Cube's SQL as `timetravel.as_of` and `repin` leave it.
        tables: The `dataset.table` names to filter (`filtered_tables`), or
            with a `path`, the fact alone.
        columns: The grain's columns on each of them; ignored with a `path`.
        dates: Per column, whether it is a date grain.
        keep: True keeps only the rows whose key `__matched` holds, so the
            caller prefixes `matched_ctes`. False keeps every row, for the
            self-check that the rewrite reproduces the run's cells.
        path: The joins that carry the grain to the fact, when it sits off it.

    Returns:
        The rewritten SQL.

    Raises:
        NotCompared: A table is not read, is read through a PIVOT or with no
            alias, or is read in a form the rewrite cannot place.
    """
    key = (
        key_sql(columns, dates)
        if path is None
        else key_sql(path.grain.columns, dates, [alias for alias, _ in path.grain.keys])
    )
    predicate = (
        # trunk-ignore(bandit/B608): the grain columns are Cube's own columns, quoted
        f"{key} IN (SELECT __key FROM __matched)" if keep else "TRUE"
    )

    def read(m: re.Match[str]) -> str:
        at = f"FOR SYSTEM_TIME AS OF TIMESTAMP '{m['at']}'"
        if path is None:
            # trunk-ignore(bandit/B608): the table is Cube's own reference and the timestamp its pinned literal
            return f"(SELECT * FROM {m['ref']} {at} WHERE {predicate}){m['alias']}"
        # Cube's ON clauses name the fact by the row SQL's alias.
        fact = f"`{path.grain.alias}`"
        return (
            # trunk-ignore(bandit/B608): the tables, joins and timestamps are Cube's own, as the run read them
            f"(SELECT {fact}.* FROM {m['ref']} AS {fact} {at}\n{path.joins}\n"
            f"WHERE {predicate}){m['alias']}"
        )

    for t in pipeline.unique(tables):
        pattern = _read_pattern(t)
        found = list(pattern.finditer(sql))
        reads = len(re.findall(re.escape(f"`{PROJECT}.{t}`"), sql, re.IGNORECASE))
        if not reads:
            raise NotCompared(f"Cube's SQL does not read {t}")
        if reads != len(found):
            # A reference left unwrapped would read every row on one side only.
            raise NotCompared(
                f"Cube's SQL reads {t} in a form the rewrite does not know"
            )
        if any(m["alias"] is None and _PIVOT_AFTER.match(sql, m.end()) for m in found):
            # `as_of` wraps a table read through a PIVOT, leaving it no alias.
            raise NotCompared(f"Cube's SQL reads {t} through a PIVOT")
        if any(m["alias"] is None for m in found):
            # Cube's columns name the table, which a subquery would hide.
            raise NotCompared(f"Cube's SQL reads {t} with no alias")
        sql = pattern.sub(read, sql)
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
    grain: Grain,
    keep: bool,
) -> str:
    """Cube's cells per cut, from its compiled cell SQL as of the build end.

    A table the dashboard's rows also read is read at the build start, as the
    run's Cube rows read it, so one query reads each table at one moment. A
    grain off the fact is reached through the joins of Cube's row SQL, each
    table read as `sides.cube_rows_sql` reads it.

    Args:
        cfg: The view's config.
        comparison: A comparison with `rows`.
        cuts: The cuts to compute, each tagged `__cut` with its label.
        build: The run's moment.
        ex: Compiles and expands the comparison's Cube SQL.
        sides: The row SQL the run reconciled for it.
        tables: The tables to filter (`filtered_tables`), or, for a grain
            with `hops`, the fact alone.
        grain: Where Cube's row SQL reads the grain (`fact_grain`).
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
    grain_dates = [p.cube in dates for p in pipeline.rows_of(comparison).grain]
    dims = [d.cube for d in comparison.dims]
    # The hops are read as the row SQL `matched_ctes` reads them, so each
    # table keeps that moment and nothing is expanded again.
    path = Path(grain, path_joins(grain, sides.cube_rows_sql)) if grain.hops else None
    parts = []
    for cut in cuts:
        sql = _pinned_cell(cfg, comparison, cut, build, ex=ex, sides=sides)
        sql = rewrite_cube_sql(
            sql, tables, grain.columns, grain_dates, keep=keep, path=path
        )
        cells = pipeline.wrap_cube(sql, cfg.view, dims, dates, comparison.measure)
        label = pipeline.lit(pipeline.cut_label(cut))
        # trunk-ignore(bandit/B608): the label is literal-escaped and the SQL the tool's own
        parts.append(f"SELECT {label} AS __cut, * FROM (\n{cells}\n)")
    return "\nUNION ALL\n".join(parts)


def _pinned_cell(
    cfg: ViewConfig,
    comparison: Comparison,
    cut: dict[str, Any],
    build: Build,
    *,
    ex: pipeline.Expand,
    sides: pipeline.RowSides,
) -> str:
    """Cube's cell SQL for `cut` as of the build end, a table the dashboard's
    rows also read moved to the build start, as the run's Cube rows read it."""
    at = ex.at(ex.cube_sql(pipeline.cell_query(cfg.view, comparison, cut)), build.end)
    shared = sorted(at.tables & sides.dashboard.tables)
    return repin(at.sql, shared, build.end, build.start)


def cube_fanout_sql(
    cfg: ViewConfig,
    comparison: Comparison,
    cuts: list[dict[str, Any]],
    build: Build,
    *,
    ex: pipeline.Expand,
    sides: pipeline.RowSides,
    grain: Grain,
) -> str:
    """The fan-out guard (`fanout_sql`) over the cells' own reads of the fact,
    for a grain with `hops`; it raises what `cube_side_sql` raises."""
    cells = [_pinned_cell(cfg, comparison, c, build, ex=ex, sides=sides) for c in cuts]
    return fanout_sql(cells, grain, sides.cube_rows_sql)


# --- the check in `sort` --------------------------------------------------------


@dataclass
class Job:
    """One comparison's formula check, planned and ready to price and run.

    `sql` holds the queries by name: `dashboard` and `cube` read matched
    rows only, `dashboard_self` and `cube_self` every row (the self-check),
    and, for a grain off the fact, `cube_fanout` the fan-out guard
    (`fanout_sql`). `stored` is the kept check of the same result this one runs again, if
    any: when this one cannot run, its verdicts stand.
    """

    comparison: str
    fingerprint: str
    cells: list[dict]
    sql: dict[str, str]
    stored: Check | None = None


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
    members = [p.cube for p in pipeline.rows_of(comparison).grain]
    grain = fact_grain(
        ex.cube_sql(pipeline.row_query(cfg.view, comparison), rows=True),
        cfg.view,
        members,
        [cfg.fact, *cfg.also_facts],
    )
    if grain.hops:
        # Cube's own joins carry the grain to the fact, the one table
        # filtered; every other table is read as Cube reads it.
        tables = [grain.table]
    else:
        compiled = "\n".join(
            ex.cube_sql(pipeline.cell_query(cfg.view, comparison, cut)) for cut in cuts
        )
        tables = filtered_tables(
            cube_read_tables(cfg, compiled),
            grain.columns,
            lambda t: wh.columns(*t.split(".", 1)),
        )
        # The grain's columns name its own table; a filtered table's
        # same-named columns may mean something else.
        if grain.table.lower() not in {t.lower() for t in tables}:
            raise NotCompared(
                f"the grain columns sit on {grain.table}, which Cube's filtered "
                "tables do not include"
            )

    def dash(keep: bool) -> str:
        return dashboard_side_sql(cfg, comparison, cuts, build, wh, keep=keep)

    def cubes(keep: bool) -> str:
        return cube_side_sql(
            cfg, comparison, cuts, build,
            ex=ex, sides=sides, tables=tables, grain=grain, keep=keep,
        )  # fmt: skip

    def matched(body: str) -> str:
        # trunk-ignore(bandit/B608): both parts are the tool's own SQL
        return f"{ctes}\nSELECT * FROM (\n{body}\n)"

    sql = {
        "dashboard": matched(dash(True)),
        "cube": matched(cubes(True)),
        "dashboard_self": dash(False),
        "cube_self": cubes(False),
    }
    if grain.hops:
        sql["cube_fanout"] = cube_fanout_sql(
            cfg, comparison, cuts, build, ex=ex, sides=sides, grain=grain
        )
    return sql


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
    (`explain.require_saved`), Cube's compiled SQL and the fact's columns.
    The check's own queries do not run here; the lookups the SQL needs (the
    network's schools, view history) can bill, under the caps and
    `maximum_bytes_billed` but outside the up-front price. Never raises:
    every failure is a check whose cells are all left to coverage under one
    reason. The run's SQL no longer
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
    """Run a planned check's queries and decide its cells (`verdicts`).

    Call inside `wh.budget`, after its dry runs are priced. Never raises: a
    BigQuery error leaves every cell to coverage under its job and reason
    code, a cap under `CAPPED`, any other error (expired credentials, say)
    under `RUN_FAILED` with the error printed, a fan-out guard whose counts
    differ under `FANS_OUT`, and rows that do not carry the comparison's dims
    under `REWRITE_DIFFERS`.
    """
    try:
        got = {k: wh.rows(sql, timeout_s=trace.TIMEOUT_S) for k, sql in job.sql.items()}
    except GoogleAPIError as exc:
        return not_compared(job.comparison, job.fingerprint, job.cells,
                            bigquery_refused(exc))  # fmt: skip
    except CostCapError:
        return not_compared(job.comparison, job.fingerprint, job.cells, CAPPED)
    except Exception as exc:  # noqa: BLE001 - the check never stops `sort`
        print(f"Formula check of {job.comparison} not run: {exc!r}")
        return not_compared(job.comparison, job.fingerprint, job.cells, RUN_FAILED)
    try:
        if any(r["__joined"] != r["__fact"] for r in got.get("cube_fanout", [])):
            return not_compared(job.comparison, job.fingerprint, job.cells,
                                FANS_OUT)  # fmt: skip
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

    def line(why: str, n: str) -> str:
        return f"{NOT_COMPARED}: {why} ({n} cells closed by coverage only)"

    for cid, check in checks.items():
        counts = {why: len(c) for why, c in check.not_compared.items() if c}
        if not counts:
            continue
        out[cid] = counts
        item = by_id.get(f"{cid}:cells")
        if item is None:
            continue
        evidence = item.get("evidence") or []
        posted = item.get("evidence_posted") or evidence
        item["evidence"] = [*(line(w, str(n)) for w, n in counts.items()), *evidence]
        item["evidence_posted"] = [
            *(line(w, mask(n)) for w, n in counts.items()),
            *posted,
        ]
    return out
