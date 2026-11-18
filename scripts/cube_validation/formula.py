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

from typing import Any

from . import pipeline, reconcile
from .bq import Warehouse
from .config import Comparison, RowSpec, ViewConfig
from .moment import Build

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
    args, kwargs = pipeline.reconcile_args(cfg, comparison, sides)
    ctes, _ = reconcile._joined(*args, keys=True, moved=True, **kwargs)
    n = len(_rows(comparison).grain)
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
