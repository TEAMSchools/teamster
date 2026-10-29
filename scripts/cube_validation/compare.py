"""Compare dashboard rows with Cube rows, and single cells.

`reconcile_sql` builds one BigQuery query that joins the two row sources on the
grain and returns counts only, so student-level rows never leave the warehouse.
The module is pure: it builds and reads strings and runs nothing.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from .config import ColumnPair, Comparison, RowSpec

BUCKETS = ("match", "value_differs", "dashboard_only", "cube_only")
_RN = "__rn"
_IN = "__in"

Verdict = Literal["pass", "differs", "dashboard_only", "cube_only"]


@dataclass(frozen=True)
class Group:
    """One non-match bucket of one result row, with every group-by column."""

    comparison_id: str
    dims: tuple[tuple[str, str], ...]
    bucket: str
    n_rows: int
    n_students: int

    def value_of(self, column: str) -> str | None:
        """The group's value in `column`; `""` names a row with no group-by."""
        if not self.dims:
            return "" if not column else None
        return dict(self.dims).get(column)


@dataclass(frozen=True)
class Gap:
    """A sheet field with no Cube member, across the view's proven sheets.

    `kind` is `cut` (on a shelf) or `filter`. `restricting` marks a filter set
    to chosen values rather than All on at least one sheet.
    """

    kind: str
    field: str
    sheets: tuple[str, ...]
    comparisons: tuple[str, ...]
    restricting: bool = False


@dataclass(frozen=True)
class CellDiff:
    """A comparison's cells that differ, with candidate causes to check.

    `counts` maps each differing verdict to its cells; `causes` are read from
    the cells, the row groups and the two definitions, never from a student.
    """

    comparison_id: str
    counts: dict[str, int]
    causes: tuple[str, ...] = ()


def _numbered(rows_sql: str, grain: list[str], values: list[str]) -> str:
    """Wrap a row source, numbering duplicates on the grain so the join cannot fan out.

    Partitions by the same keys the join compares (`_grain_keys`), so both
    sides number 1 and 1.0, or a NULL past the student column, as one value.
    """
    order = ", ".join(values or grain)
    partition = ", ".join(_grain_keys(grain))
    return (
        # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from Cube's compiled query
        f"SELECT s.*, TRUE AS {_IN}, "
        f"ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {order}) "
        f"AS {_RN}\n  FROM (\n{rows_sql}\n  ) AS s"
    )


def _bool_text(col: str) -> str:
    text = f"CAST({col} AS STRING)"
    return (
        f"CASE LOWER({text}) WHEN 'true' THEN '1' WHEN 'false' THEN '0' ELSE {text} END"
    )


def _pair_matches(d: str, c: str) -> str:
    """Null-safe, type-tolerant equality of one dashboard/cube value pair."""
    # Cast through STRING: SAFE_CAST(BOOL AS FLOAT64) fails at compile time.
    # TRUE and FALSE read as 1 and 0 so a BOOL matches a 0/1 column.
    number_d = f"SAFE_CAST({_bool_text(d)} AS FLOAT64)"
    number_c = f"SAFE_CAST({_bool_text(c)} AS FLOAT64)"
    return (
        f"COALESCE(({d} IS NULL AND {c} IS NULL) "
        f"OR {number_d} = {number_c} "
        f"OR (({number_d} IS NULL OR {number_c} IS NULL) "
        f"AND LOWER(CAST({d} AS STRING)) = LOWER(CAST({c} AS STRING))), FALSE)"
    )


def _key(col: str) -> str:
    """Join key that treats 1, 1.0 and '1' alike; non-numbers compare as text."""
    text = f"CAST({col} AS STRING)"
    return f"COALESCE(CAST(SAFE_CAST({text} AS FLOAT64) AS STRING), {text})"


def _grain_key(col: str) -> str:
    """`_key` made null-safe: a NULL keys as '' and a value, '' included, as '=<key>'.

    A grain column past the student is an identity, so a NULL on both sides is
    the same row. An equality rather than `OR ... IS NULL` keeps the FULL
    OUTER JOIN hashable.
    """
    return f"IFNULL(CONCAT('=', {_key(col)}), '')"


def _grain_keys(grain: list[str]) -> list[str]:
    """One join key per grain column: plain `_key` for the first, the student.

    A NULL student never matches: rows with no id would otherwise pair up by
    value order and read as matches. Every later column is null-safe.
    """
    return [_key(grain[0]), *(_grain_key(g) for g in grain[1:])]


def reconcile_sql(
    cube_rows_sql: str,
    dashboard_rows_sql: str,
    rows: RowSpec,
    group_by: list[ColumnPair],
    filters: Sequence[tuple[str, str]] = (),
) -> str:
    """Build the query that classifies every row as match, differs or one-sided.

    Rows are joined on the grain plus a per-grain duplicate number. The cube
    source names its columns by each pair's `cube` name and the dashboard
    source by its `dashboard` name. Numeric grain keys join across types (1,
    1.0 and '1'); anything else joins as text. A NULL in the first grain
    column, the student, never matches. A NULL in a later grain column
    matches a NULL on the other side and nothing else, the empty string
    included.
    Temporal grains are not normalized: callers must emit date grains as DATE
    on both sides.

    Args:
        cube_rows_sql: SELECT returning the grain, value and group-by columns
            under their `cube` names.
        dashboard_rows_sql: The same, under their `dashboard` names.
        rows: The grain and value column pairs.
        group_by: Columns to break counts out by; each is named by its `cube`
            name in the result and read from whichever side has the row.
        filters: For each dashboard-only filter, the dashboard rows' boolean
            column that says it keeps a row, and the label to name it by. A row
            one drops that Cube has reads `dashboard_filtered`, with the label
            in `__filter`; one Cube lacks too is a match.

    Returns:
        One query returning `bucket`, each group-by column, `n_rows` and
        `n_students` (distinct values of the first grain pair). No grain or
        value column is returned.
    """
    ctes, group_names = _joined(
        cube_rows_sql, dashboard_rows_sql, rows, group_by, filters
    )
    outer_select = ", ".join(
        ["bucket", *group_names, "COUNT(*) AS n_rows"]
        + ["COUNT(DISTINCT __student) AS n_students"]
    )
    group_clause = ", ".join(["bucket", *group_names])
    return (
        ctes
        + "\n-- outer\n"
        # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from Cube's compiled query
        + f"SELECT {outer_select}\nFROM joined\n"
        + f"GROUP BY {group_clause}\nORDER BY {group_clause}"
    )


def _joined(
    cube_rows_sql: str,
    dashboard_rows_sql: str,
    rows: RowSpec,
    group_by: list[ColumnPair],
    filters: Sequence[tuple[str, str]],
    keys: bool = False,
) -> tuple[str, list[str]]:
    """The `c`, `d` and `joined` CTEs of `reconcile_sql`, and the group columns.

    With `keys`, `joined` also carries each one-sided row's grain keys
    (`__k0`, ...) and duplicate number (`__rn`), for `trace_sql`.
    """
    cube_grain = [p.cube for p in rows.grain]
    dash_grain = [p.dashboard for p in rows.grain]

    on = [f"c.{_RN} = d.{_RN}"] + [
        f"{c} = {d}"
        for c, d in zip(
            _grain_keys([f"c.{g}" for g in cube_grain]),
            _grain_keys([f"d.{g}" for g in dash_grain]),
            strict=True,
        )
    ]
    same = [_pair_matches(f"d.{p.dashboard}", f"c.{p.cube}") for p in rows.values]
    all_same = " AND ".join(same) or "TRUE"

    group_cols = [
        f"COALESCE(CAST(c.{p.cube} AS STRING), CAST(d.{p.dashboard} AS STRING)) "
        f"AS {p.cube}"
        for p in group_by
    ]
    group_names = [p.cube for p in group_by]
    first = rows.grain[0]

    kept = " AND ".join(f"d.{flag}" for flag, _ in filters)
    dropped = (
        [f"WHEN c.{_IN} IS NULL AND d.{_IN} IS NOT NULL AND NOT ({kept}) THEN 'match' "]
        if filters
        else []
    )
    filtered = [f"WHEN NOT ({kept}) THEN 'dashboard_filtered' "] if filters else []
    if filters:
        which = " ".join(f"WHEN NOT d.{flag} THEN '{label}'" for flag, label in filters)
        group_cols = [
            f"CASE WHEN c.{_IN} IS NOT NULL AND d.{_IN} IS NOT NULL THEN "
            f"CASE {which} END END AS __filter",
            *group_cols,
        ]
        group_names = ["__filter", *group_names]
    joined_select = ",\n    ".join(
        [
            "CASE " + "".join(dropped) + f"WHEN c.{_IN} IS NULL THEN 'dashboard_only' "
            f"WHEN d.{_IN} IS NULL THEN 'cube_only' "
            + "".join(filtered)
            + f"WHEN NOT ({all_same}) THEN 'value_differs' "
            "ELSE 'match' END AS bucket",
            f"COALESCE(CAST(c.{first.cube} AS STRING), "
            f"CAST(d.{first.dashboard} AS STRING)) AS __student",
            *group_cols,
            *(
                [
                    f"IF(c.{_IN} IS NULL, {d}, {c}) AS __k{i}"
                    for i, (c, d) in enumerate(
                        zip(
                            _grain_keys([f"c.{g}" for g in cube_grain]),
                            _grain_keys([f"d.{g}" for g in dash_grain]),
                            strict=True,
                        )
                    )
                ]
                + [f"COALESCE(c.{_RN}, d.{_RN}) AS {_RN}"]
                if keys
                else []
            ),
        ]
    )

    return (
        # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from Cube's compiled query
        "WITH c AS (\n  "
        + _numbered(cube_rows_sql, cube_grain, [p.cube for p in rows.values])
        # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from Cube's compiled query
        + "\n),\nd AS (\n  "
        + _numbered(dashboard_rows_sql, dash_grain, [p.dashboard for p in rows.values])
        # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from Cube's compiled query
        + "\n),\njoined AS (\n  SELECT\n    "
        + joined_select
        + "\n  FROM c\n  FULL OUTER JOIN d\n    ON "
        + "\n    AND ".join(on)
        + "\n)"
    ), group_names


# Trace output step ids that are not steps. A row no variant recovers; a row
# several recover (`*a|b`, their ids); a row the other side has more than once
# (`=`, never attributed); and prefixes: a row a table's unrelaxed SQL
# already returns (`!`), and a row only a presence check returns (`#`).
NONE = ""
MANY = "*"
DUPLICATE = "="
UNREPRODUCED = "!"
PRESENT = "#"
_SEP = "|"


def trace_sql(
    cube_rows_sql: str,
    dashboard_rows_sql: str,
    rows: RowSpec,
    group_by: list[ColumnPair],
    filters: Sequence[tuple[str, str]] = (),
    *,
    bucket: str,
    side: str,
    variants: Sequence[tuple[str, str]],
    exclude: Sequence[str] = (),
    include: Sequence[str] = (),
    combine: bool = True,
) -> str:
    """Build the query that counts which relaxed variants recover each unmatched row.

    The unmatched rows are rebuilt inside the query exactly as `reconcile_sql`
    finds them, so no row leaves BigQuery: the result has the group columns,
    a step id and a count, nothing else. A variant recovers a row when it
    returns the row's grain (by the reconcile's keys and NULL rules). A row
    whose grain the other side holds more than once (duplicate number past
    1) is never traced: any step that fans out would "recover" it.

    Args:
        cube_rows_sql: The Cube rows the run reconciled.
        dashboard_rows_sql: The dashboard rows the run reconciled.
        rows: The grain and value column pairs.
        group_by: The group-by columns, as `reconcile_sql` takes them.
        filters: The dashboard-only filter flags, as `reconcile_sql` takes
            them, so the rows bucket as the run's did.
        bucket: `cube_only` or `dashboard_only`: the rows to trace.
        side: The side the variants rewrite: `dashboard` (for Cube-only
            rows) or `cube`. Their grain columns carry that side's names.
        variants: `(step_id, rows_sql)` per relaxed variant. An id starting
            with `UNREPRODUCED` marks a table's unrelaxed SQL: a row it
            recovers is counted under that id whatever else recovers it. An
            id starting with `PRESENT` marks a presence check: it counts a
            row only when no step recovers it.
        exclude: Variants whose recovered rows are left out first, because
            a shallower level already explained them.
        include: Variants a row must be recovered by to stay in play.
        combine: True counts each row once: under the one step that recovers
            it, `MANY` plus the ids of the several that do, a `PRESENT` id, or
            `NONE`; then, under `+<step id>`, every row each variant
            recovers. False counts each step's rows separately, plus every
            row in play under `NONE`. Both count, under `DUPLICATE`, the rows
            left out for a duplicate grain.

    Returns:
        One query returning `bucket`, each group-by column, `step_id` and
        `n_rows`.
    """
    ctes, group_names = _joined(
        cube_rows_sql, dashboard_rows_sql, rows, group_by, filters, keys=True
    )
    group_names = [g for g in group_names if g != "__filter"]
    grain = [p.cube if side == "cube" else p.dashboard for p in rows.grain]
    n = len(grain)
    keys = [f"__k{i}" for i in range(n)]
    item = ["bucket", *group_names]

    def keyed(name: str, sql: str) -> str:
        cols = ", ".join(
            f"{k} AS {kn}" for k, kn in zip(_grain_keys(grain), keys, strict=True)
        )
        return (
            # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from Cube's compiled query
            f"{name} AS (\n  SELECT DISTINCT {cols}\n  FROM (\n{sql}\n  ) AS s\n)"
        )

    def matches(v: str, u: str) -> str:
        return " AND ".join(f"{v}.{k} = {u}.{k}" for k in keys)

    parts = [
        ctes,
        # trunk-ignore(bandit/B608): the bucket is one of BUCKETS
        f"u AS (\n  SELECT {', '.join(item + keys)}, {_RN}, "
        f"FARM_FINGERPRINT(TO_JSON_STRING(STRUCT({', '.join(keys)}, {_RN}))) AS __row\n"
        f"  FROM joined WHERE bucket = '{bucket}'\n)",
    ]
    parts += [keyed(f"x{i}", sql) for i, sql in enumerate(exclude)]
    parts += [keyed(f"i{i}", sql) for i, sql in enumerate(include)]
    keep = [f"{_RN} = 1"]
    keep += [
        # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from the run's own SQL
        f"NOT EXISTS (SELECT 1 FROM x{i} WHERE {matches(f'x{i}', 'u')})"
        for i in range(len(exclude))
    ]
    keep += [
        # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from the run's own SQL
        f"EXISTS (SELECT 1 FROM i{i} WHERE {matches(f'i{i}', 'u')})"
        for i in range(len(include))
    ]
    # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from the run's own SQL
    parts.append(f"p AS (\n  SELECT * FROM u WHERE {' AND '.join(keep)}\n)")
    parts += [keyed(f"v{i}", sql) for i, (_, sql) in enumerate(variants)]
    hits = (
        "\n  UNION ALL\n  ".join(
            # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from the run's own SQL
            f"SELECT p.__row, '{step_id}' AS step_id FROM p JOIN v{i} ON {matches(f'v{i}', 'p')}"
            for i, (step_id, _) in enumerate(variants)
        )
        or "SELECT CAST(NULL AS INT64) AS __row, '' AS step_id FROM (SELECT 1) WHERE FALSE"
    )
    parts.append(f"hits AS (\n  {hits}\n)")
    group_clause = ", ".join(item + ["step_id"])
    duplicates = (
        # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from the run's own SQL
        f"  UNION ALL SELECT {', '.join(item)}, '{DUPLICATE}' AS step_id "
        f"FROM u WHERE {_RN} > 1\n"
    )
    if combine:
        step = f"IF(STARTS_WITH(step_id, '{PRESENT}'), NULL, step_id)"
        parts.append(
            # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from the run's own SQL
            "per_row AS (\n  SELECT __row, CASE "
            f"WHEN LOGICAL_OR(STARTS_WITH(step_id, '{UNREPRODUCED}')) "
            f"THEN MIN(IF(STARTS_WITH(step_id, '{UNREPRODUCED}'), step_id, NULL)) "
            f"WHEN COUNT(DISTINCT {step}) = 1 THEN MIN({step}) "
            f"WHEN COUNT(DISTINCT {step}) > 1 THEN CONCAT('{MANY}', "
            f"STRING_AGG(DISTINCT {step}, '{_SEP}' ORDER BY {step})) "
            f"ELSE MIN(IF(STARTS_WITH(step_id, '{PRESENT}'), step_id, NULL)) "
            "END AS step_id\n  FROM hits GROUP BY __row\n)"
        )
        # Then every row each variant recovers, `+`-prefixed, so the caller
        # knows which variants explain anything, ambiguous rows included.
        outer = (
            # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from the run's own SQL
            f"SELECT {', '.join(item)}, step_id, COUNT(*) AS n_rows\n"
            "FROM (\n"
            f"  SELECT {', '.join(f'p.{c}' for c in item)}, "
            f"IFNULL(per_row.step_id, '{NONE}') AS step_id "
            "FROM p LEFT JOIN per_row USING (__row)\n"
            f"  UNION ALL SELECT {', '.join(f'p.{c}' for c in item)}, "
            "CONCAT('+', hits.step_id) AS step_id FROM p JOIN hits USING (__row)\n"
            + duplicates
            + ")\n"
            f"GROUP BY {group_clause}"
        )
    else:
        outer = (
            # trunk-ignore(bandit/B608): identifiers are validated in config.py; row SQL comes from the run's own SQL
            f"SELECT {', '.join(item)}, step_id, COUNT(*) AS n_rows\n"
            "FROM (\n"
            f"  SELECT {', '.join(f'p.{c}' for c in item)}, hits.step_id "
            "FROM p JOIN hits USING (__row)\n"
            f"  UNION ALL SELECT {', '.join(item)}, '{NONE}' AS step_id FROM p\n"
            + duplicates
            + ")\n"
            f"GROUP BY {group_clause}"
        )
    return ",\n".join(parts) + "\n-- outer\n" + outer


def many_ids(step_id: str) -> list[str]:
    """The step ids a `MANY` id lists."""
    return [s for s in step_id[len(MANY) :].split(_SEP) if s]


def groups_from(comparison_id: str, result_rows: list[dict]) -> list[Group]:
    """Turn `reconcile_sql` result rows into groups, leaving out the matches.

    Args:
        comparison_id: The comparison the rows belong to.
        result_rows: Rows from the query, each with `bucket`, `n_rows`,
            `n_students` and any group-by columns.

    Returns:
        One `Group` per non-match row, carrying all its group-by columns in
        query order, so a row's students are counted once. A NULL value
        becomes an empty string.
    """
    reserved = {"bucket", "n_rows", "n_students", "__filter"}
    return [
        Group(
            comparison_id=comparison_id,
            # The dashboard-only filter that dropped the rows, on its rows only.
            dims=(
                (("dashboard_filter", str(row["__filter"])),)
                if row.get("__filter") is not None
                else ()
            )
            + tuple(
                (k, "" if v is None else str(v))
                for k, v in row.items()
                if k not in reserved
            ),
            bucket=row["bucket"],
            n_rows=int(row["n_rows"]),
            n_students=int(row["n_students"]),
        )
        for row in result_rows
        if row["bucket"] != "match"
    ]


# Config operator names that Cube spells differently.
_CUBE_OPERATORS = {"not_equals": "notEquals"}


def scope_filters(comparison: Comparison) -> list[dict[str, Any]]:
    """Return the Cube filters for each `scope` entry of a comparison.

    Args:
        comparison: A comparison whose `scope` entries are
            `{cube: <member>, values: [...]}` (operator `equals`, the default),
            another operator in `config.SCOPE_OPERATORS`, or
            `{cube: <member>, operator: set}` (not null).

    Returns:
        One filter per entry, values as the strings Cube takes.
    """
    out = []
    for entry in comparison.scope:
        operator = entry.get("operator", "equals")
        f: dict[str, Any] = {
            "member": entry["cube"],
            "operator": _CUBE_OPERATORS.get(operator, operator),
        }
        if operator != "set":
            f["values"] = [
                str(v).lower() if isinstance(v, bool) else str(v)
                for v in entry["values"]
            ]
        out.append(f)
    return out


# Float noise sits past this digit: BigQuery's AVG gives 15/16 as
# 0.9374999999999999, which must round like 0.9375 at a half-way tie.
NOISE_DECIMALS = 9


def _half_up(x: float, decimals: int) -> Decimal:
    """Round the way a dashboard displays: half up on the decimal text, after
    dropping float noise past `NOISE_DECIMALS`.
    """
    clean = Decimal(repr(x)).quantize(Decimal(1).scaleb(-NOISE_DECIMALS), ROUND_HALF_UP)
    return clean.quantize(Decimal(1).scaleb(-decimals), ROUND_HALF_UP)


def cell_verdict(dashboard: float | None, cube: float | None, decimals: int) -> Verdict:
    """Compare two cells as the dashboard displays them.

    Args:
        dashboard: The dashboard value, or None when it shows nothing.
        cube: The Cube value, or None.
        decimals: Digits kept before comparing; for a percent, already counts
            the fraction digits.

    Returns:
        `pass` when both round to the same value (or both are missing),
        `dashboard_only` or `cube_only` when one side is missing, else
        `differs`.
    """
    if dashboard is None and cube is None:
        return "pass"
    if cube is None:
        return "dashboard_only"
    if dashboard is None:
        return "cube_only"
    return (
        "pass"
        if _half_up(dashboard, decimals) == _half_up(cube, decimals)
        else "differs"
    )


_TOKEN = re.compile(
    r"(?P<comment>--[^\n]*)|(?P<string>'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\""
    r"|`[^`]*`)|(?P<word>\w+)|(?P<open>\()|(?P<close>\))|(?P<other>[^\s\w()]+)"
)
_OPENERS = {"where", "qualify", "having", "on"}
_ENDERS = {
    "select", "from", "where", "group", "order", "qualify", "having", "window",
    "limit", "union", "intersect", "except", "join", "left", "right", "inner",
    "full", "cross", "using",
}  # fmt: skip


def _tokens(sql: str) -> list[tuple[str, str, bool]]:
    """Return (kind, text, preceded_by_space) for each non-comment token."""
    out = []
    end = 0
    for m in _TOKEN.finditer(sql):
        if m.lastgroup == "comment":
            end = m.end()
            continue
        out.append((m.lastgroup or "", m.group(), m.start() > end))
        end = m.end()
    return out


def clauses_for(columns: list[str], sql: str) -> list[str]:
    """Find the filter predicates in a query that name any of the columns.

    Looks at each `WHERE`, `QUALIFY`, `HAVING` and `JOIN ... ON` clause at any
    nesting depth and splits it on top-level `AND` only (not inside
    parentheses, `BETWEEN ... AND` or `CASE`).

    Args:
        columns: Column names to look for, matched as whole words.
        sql: The query text.

    Returns:
        The matching predicates in order, each collapsed to one line.
    """
    wanted = {c.lower() for c in columns}
    toks = _tokens(sql)
    found: list[str] = []

    for i, (kind, text, _) in enumerate(toks):
        if kind != "word" or text.lower() not in _OPENERS:
            continue

        depth = 0
        case_depth = 0
        between = False
        current: list[tuple[str, str, bool]] = []
        predicates: list[list[tuple[str, str, bool]]] = []
        for tok in toks[i + 1 :]:
            tkind, ttext, _ = tok
            low = ttext.lower()
            if tkind == "open":
                depth += 1
            elif tkind == "close":
                if depth == 0:
                    break
                depth -= 1
            elif tkind == "other" and ttext == ";" and depth == 0:
                break
            elif tkind == "word" and depth == 0:
                if low in _ENDERS:
                    break
                if low == "case":
                    case_depth += 1
                elif low == "end" and case_depth:
                    case_depth -= 1
                elif low == "between" and not case_depth:
                    between = True
                elif low == "and" and not case_depth:
                    if between:
                        between = False
                    else:
                        predicates.append(current)
                        current = []
                        continue
            current.append(tok)
        predicates.append(current)

        for predicate in predicates:
            names = {t.lower() for k, t, _ in predicate if k == "word"}
            if names & wanted:
                found.append(
                    "".join(
                        (" " if space and n else "") + text
                        for n, (_, text, space) in enumerate(predicate)
                    )
                )
    return found
