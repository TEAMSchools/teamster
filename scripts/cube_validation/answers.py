"""Pick the example cell an owner checks by hand and pin each side's SQL to it.

The owner pastes these queries into the BigQuery console under their own access,
and the texts go into a GitHub issue, so the example is never one person's row:
every dimension is a reviewed column and at least `MASK_BELOW` students stand
behind it. This module runs no queries; it selects and formats saved data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from .config import ViewConfig
from .cube_client import _literal
from .report import MASK_BELOW, RunResult, _is_identifier

# BigQuery keeps table history this long, so an as-of query stops working then.
TIME_TRAVEL_DAYS = 7


@dataclass(frozen=True)
class HandCheck:
    comparison: str
    cut: str
    dims: tuple[tuple[str, str], ...]
    dashboard: float | None
    cube: float | None
    dashboard_sql: str
    cube_sql: str
    dashboard_usd: float
    cube_usd: float
    expires: datetime
    expired: bool


def example_cell(run: RunResult, comparison: str) -> dict | None:
    """Pick the differing cell an owner can check without seeing a person.

    Args:
        run: The saved run.
        comparison: The comparison id.

    Returns:
        The cell with the largest absolute difference whose dims are all
        reviewed columns and whose `n_students` is at least `MASK_BELOW`; ties
        go to the lowest `key`. None when no cell qualifies.
    """
    ok = [
        c
        for c in run.diff_cells
        if c["comparison"] == comparison
        and not any(_is_identifier(column) for column, _ in c["dims"])
        and c["n_students"] is not None
        and c["n_students"] >= MASK_BELOW
        and c["dashboard"] is not None
        and c["cube"] is not None
    ]
    if not ok:
        return None
    return min(ok, key=lambda c: (-abs(c["dashboard"] - c["cube"]), c["key"]))


def _predicate(column: str, key: str) -> str:
    """Match a column against the text `pipeline._key` made of its value.

    `_key` writes NULL as '', numbers as plain decimals and booleans as
    True/False, so a bare `column = '7'` fails on a number and `= ''` misses a
    NULL. A date or text key compares as a string literal, which BigQuery
    coerces against a DATE or TIMESTAMP column.
    """
    if key == "":
        return f"{column} IS NULL"
    if key.lower() in ("true", "false"):
        return f"LOWER(CAST({column} AS STRING)) = {_literal(key.lower())}"
    try:
        number = Decimal(key)
    except InvalidOperation:
        number = None
    if number is not None and number.is_finite():
        return f"SAFE_CAST({column} AS NUMERIC) = {format(number.normalize(), 'f')}"
    return f"{column} = {_literal(key)}"


def _pinned(sql: str, pairs: list[tuple[str, str]]) -> str:
    """Wrap `sql` to the cell; unchanged for a total cell with no dims."""
    if not pairs:
        return sql
    where = " AND ".join(_predicate(name, value) for name, value in pairs)
    # trunk-ignore(bandit/B608): names come from validated config and values are literal-escaped
    return f"SELECT * FROM (\n{sql}\n) WHERE {where}"


def hand_check(
    run: RunResult, cfg: ViewConfig, comparison: str, now: datetime
) -> HandCheck | None:
    """Wrap each side's saved as-of SQL to return just the example cell.

    The Cube side outputs Cube member names; the dashboard side outputs the
    dashboard column names, which `cfg` maps from the member names.

    Args:
        run: The saved run.
        cfg: The view's config, for the dashboard column names.
        comparison: The comparison id.
        now: The current time, to decide whether the as-of SQL still runs.

    Returns:
        None when there is no example cell, no saved SQL or `cell_sql_usd`
        entry for its cut, or a dim the comparison does not map.
    """
    cell = example_cell(run, comparison)
    cmp = next((c for c in cfg.comparisons if c.id == comparison), None)
    sql = run.cell_sql.get(comparison, {}).get(cell["cut"]) if cell else None
    usd = run.cell_sql_usd.get(comparison, {}).get(cell["cut"]) if cell else None
    if not (cell and cmp and sql and usd):
        return None
    names = {d.cube: d.dashboard for d in cmp.dims}
    if any(member not in names for member, _ in cell["dims"]):
        return None
    cube_pairs = [(member, value) for member, value in cell["dims"]]
    dash_pairs = [(names[member], value) for member, value in cell["dims"]]
    expires = run.moment.start + timedelta(days=TIME_TRAVEL_DAYS)
    return HandCheck(
        comparison=comparison,
        cut=cell["cut"],
        dims=tuple(cube_pairs),
        dashboard=cell["dashboard"],
        cube=cell["cube"],
        dashboard_sql=_pinned(sql[0], dash_pairs),
        cube_sql=_pinned(sql[1], cube_pairs),
        dashboard_usd=usd[0],
        cube_usd=usd[1],
        expires=expires,
        expired=now >= expires,
    )
