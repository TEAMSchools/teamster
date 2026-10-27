"""Compare dashboard rows with Cube rows, and single cells.

`reconcile_sql` builds one BigQuery query that joins the two row sources on the
grain and returns counts only, so student-level rows never leave the warehouse.
The module is pure: it builds and reads strings and runs nothing.
"""

from __future__ import annotations

import re
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
    comparison_id: str
    column: str
    value: str
    bucket: str
    n_rows: int
    n_students: int


def _numbered(rows_sql: str, grain: list[str], values: list[str]) -> str:
    """Wrap a row source, numbering duplicates on the grain so the join cannot fan out."""
    order = ", ".join(values or grain)
    return (
        f"SELECT s.*, TRUE AS {_IN}, "
        f"ROW_NUMBER() OVER (PARTITION BY {', '.join(grain)} ORDER BY {order}) "
        f"AS {_RN}\n  FROM (\n{rows_sql}\n  ) AS s"
    )


def _pair_matches(d: str, c: str) -> str:
    """Null-safe, type-tolerant equality of one dashboard/cube value pair."""
    # Cast through STRING: SAFE_CAST(BOOL AS FLOAT64) fails at compile time.
    number_d = f"SAFE_CAST(CAST({d} AS STRING) AS FLOAT64)"
    number_c = f"SAFE_CAST(CAST({c} AS STRING) AS FLOAT64)"
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


def reconcile_sql(
    cube_rows_sql: str,
    dashboard_rows_sql: str,
    rows: RowSpec,
    group_by: list[ColumnPair],
) -> str:
    """Build the query that classifies every row as match, differs or one-sided.

    Rows are joined on the grain plus a per-grain duplicate number. The cube
    source names its columns by each pair's `cube` name and the dashboard
    source by its `dashboard` name. Numeric grain keys join across types (1,
    1.0 and '1'); anything else joins as text, and a NULL grain value never
    matches. Temporal grains are not normalized: callers must emit date grains
    as DATE on both sides.

    Args:
        cube_rows_sql: SELECT returning the grain, value and group-by columns
            under their `cube` names.
        dashboard_rows_sql: The same, under their `dashboard` names.
        rows: The grain and value column pairs.
        group_by: Columns to break counts out by; each is named by its `cube`
            name in the result and read from whichever side has the row.

    Returns:
        One query returning `bucket`, each group-by column, `n_rows` and
        `n_students` (distinct values of the first grain pair). No grain or
        value column is returned.
    """
    cube_grain = [p.cube for p in rows.grain]
    dash_grain = [p.dashboard for p in rows.grain]

    on = [f"c.{_RN} = d.{_RN}"] + [
        f"{_key(f'c.{p.cube}')} = {_key(f'd.{p.dashboard}')}" for p in rows.grain
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

    joined_select = ",\n    ".join(
        [
            f"CASE WHEN c.{_IN} IS NULL THEN 'dashboard_only' "
            f"WHEN d.{_IN} IS NULL THEN 'cube_only' "
            f"WHEN NOT ({all_same}) THEN 'value_differs' "
            "ELSE 'match' END AS bucket",
            f"COALESCE(CAST(c.{first.cube} AS STRING), "
            f"CAST(d.{first.dashboard} AS STRING)) AS __student",
            *group_cols,
        ]
    )
    outer_select = ", ".join(
        ["bucket", *group_names, "COUNT(*) AS n_rows"]
        + ["COUNT(DISTINCT __student) AS n_students"]
    )
    group_clause = ", ".join(["bucket", *group_names])

    return (
        "WITH c AS (\n  "
        + _numbered(cube_rows_sql, cube_grain, [p.cube for p in rows.values])
        + "\n),\nd AS (\n  "
        + _numbered(dashboard_rows_sql, dash_grain, [p.dashboard for p in rows.values])
        + "\n),\njoined AS (\n  SELECT\n    "
        + joined_select
        + "\n  FROM c\n  FULL OUTER JOIN d\n    ON "
        + "\n    AND ".join(on)
        + "\n)\n-- outer\n"
        + f"SELECT {outer_select}\nFROM joined\n"
        + f"GROUP BY {group_clause}\nORDER BY {group_clause}"
    )


def groups_from(comparison_id: str, result_rows: list[dict]) -> list[Group]:
    """Turn `reconcile_sql` result rows into groups, leaving out the matches.

    Args:
        comparison_id: The comparison the rows belong to.
        result_rows: Rows from the query, each with `bucket`, `n_rows`,
            `n_students` and any group-by columns.

    Returns:
        One `Group` per non-match bucket and group-by column; a row with no
        group-by column has an empty `column` and `value`. A NULL value
        becomes an empty string.
    """
    reserved = {"bucket", "n_rows", "n_students"}
    groups = []
    for row in result_rows:
        if row["bucket"] == "match":
            continue
        columns = [k for k in row if k not in reserved] or [""]
        for column in columns:
            value = row.get(column) if column else None
            groups.append(
                Group(
                    comparison_id=comparison_id,
                    column=column,
                    value="" if value is None else str(value),
                    bucket=row["bucket"],
                    n_rows=int(row["n_rows"]),
                    n_students=int(row["n_students"]),
                )
            )
    return groups


def scope_filters(comparison: Comparison) -> list[dict[str, Any]]:
    """Return the Cube filters for each `scope` entry of a comparison.

    Args:
        comparison: A comparison whose `scope` entries are
            `{cube: <member>, values: [...]}`.

    Returns:
        One `equals` filter per entry.
    """
    return [
        {"member": entry["cube"], "operator": "equals", "values": entry["values"]}
        for entry in comparison.scope
    ]


def _half_up(x: float, decimals: int) -> Decimal:
    """Round the way a dashboard displays: half up on the decimal text."""
    return Decimal(repr(x)).quantize(Decimal(1).scaleb(-decimals), ROUND_HALF_UP)


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
