"""Place a comparison's row groups in its differing cells.

A differing cell is covered when every group with a row in it is proven or
decided. Placing must be exact, or a cell would close with no proven row in it:
a group is in a cell only when, under the cell's cut, a side holds its rows
(`Group.cut_rows`) and that side files them under the cell's every dim. Pure:
no I/O.
"""

from __future__ import annotations

from . import pipeline, reconcile
from .config import Comparison
from .reconcile import Group

# Why a cell whose groups carry no rows per cut cannot be placed: a run saved
# before they were kept. No count is not 0 rows.
NOT_RECORDED = "its groups' rows per cut are not recorded; run the comparison again"


def unplaceable(comparison: Comparison) -> str | None:
    """Why no cell of the comparison can be placed, or None.

    Returns:
        `the comparison has no rows` without `rows`; `its dims <names> are
        part of the row grain` when a cell dim is not one a group splits by
        (`pipeline.group_dims`); else None.
    """
    if comparison.rows is None:
        return "the comparison has no rows"
    split = {p.cube for p in pipeline.group_dims(comparison)}
    grain = [d.cube for d in comparison.dims if d.cube not in split]
    if grain:
        return f"its dims {', '.join(grain)} are part of the row grain"
    return None


def _dash(g: Group, column: str) -> str | None:
    """The column's value on the dashboard side: its `d:` column when the
    group has them (the 2 sides file its rows in different cells), else its
    own."""
    if any(c.startswith(reconcile.DASH_PREFIX) for c, _ in g.dims):
        return g.value_of(f"{reconcile.DASH_PREFIX}{column}")
    return g.value_of(column)


def _agrees(value_of, dims) -> bool:
    """Whether every cell dim holds the value `value_of` gives its column."""
    return all(
        value_of(column) is not None
        and pipeline._key(value_of(column)) == pipeline._key(value)
        for column, value in dims
    )


def _could_hold(g: Group, cell: dict) -> bool:
    """Whether either side files the group under the cell's dims, any cut."""
    dims = cell["dims"]
    return _agrees(g.value_of, dims) or _agrees(lambda c: _dash(g, c), dims)


def has_rows_in(g: Group, cell: dict) -> bool:
    """Whether the group has at least 1 row in the cell.

    Under the cell's cut, its Cube-side rows are more than 0 and its own
    columns agree with every cell dim, or its dashboard-side rows are more
    than 0 and the dashboard's columns (its `d:` ones when it has them)
    agree. Values compare by `pipeline._key`. A group with no `cut_rows`
    entry for the cell's cut has no row there.
    """
    cut = cell.get("cut", "{}")
    counts = [(c, d) for label, c, d in g.cut_rows if label == cut]
    if not counts:
        return False
    cube_rows, dash_rows = counts[0]
    dims = cell["dims"]
    return (cube_rows > 0 and _agrees(g.value_of, dims)) or (
        dash_rows > 0 and _agrees(lambda c: _dash(g, c), dims)
    )


def unplaced(cell: dict, groups: list[Group], comparison: Comparison) -> str | None:
    """Why the cell cannot be placed, or None.

    `unplaceable`'s reason; a cell dim a group of the comparison does not
    split by; or `NOT_RECORDED` when a group either side files under the
    cell's dims carries no rows per cut.
    """
    if why := unplaceable(comparison):
        return why
    mine = [g for g in groups if g.comparison_id == comparison.id]
    missing = [
        column
        for column, _ in cell["dims"]
        if any(g.value_of(column) is None or _dash(g, column) is None for g in mine)
    ]
    if missing:
        return f"its groups do not split by {', '.join(dict.fromkeys(missing))}"
    if any(not g.cut_rows and _could_hold(g, cell) for g in mine):
        return NOT_RECORDED
    return None


def placed(
    cell: dict, groups: list[Group], comparison: Comparison
) -> list[Group] | None:
    """The comparison's groups with a row in the cell, in `groups` order.

    Returns:
        None when the cell cannot be placed (`unplaced`); `[]` when no
        unmatched row lies in it.
    """
    if unplaced(cell, groups, comparison) is not None:
        return None
    return [
        g for g in groups if g.comparison_id == comparison.id and has_rows_in(g, cell)
    ]
