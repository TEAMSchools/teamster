"""Diagnosis probes: analyst SQL that recomputes a cell two ways over the extract."""

from __future__ import annotations

from dataclasses import dataclass

from . import cells as cells_mod
from .cells import Cell, Format
from .config import Checks, Probe
from .rows import TAB

JUDGED = (
    cells_mod.PASS,
    cells_mod.COINCIDENTAL,
    cells_mod.ROW_GAP,
    cells_mod.FORMULA_GAP,
)


@dataclass
class ProbeCell:
    cut: str
    sheet: str
    dims: dict[str, str]
    dashboard: float | None
    candidate: float | None
    reproduces: bool
    candidate_matches_cube: bool
    error: str = ""


@dataclass
class ProbeResult:
    probe: str
    proven: bool
    cells: list[ProbeCell]


def shows_same(
    value: float | None, other: float | None, tableau: str | None, fmt: Format | None
) -> bool:
    """Whether two numbers show the same on the dashboard.

    Both are in Cube's units (a fraction when the dashboard shows a percent).
    They round half up to the dashboard's decimals; without a format, to the
    export's own decimals and percent sign.
    """
    d = cells_mod.parse_display(tableau)
    if value is None or other is None or d is None:
        return False
    percent, decimals = (fmt.percent, fmt.decimals) if fmt else (d.percent, d.decimals)
    k = 100 if percent else 1
    return cells_mod._half_up(value * k, decimals) == cells_mod._half_up(
        other * k, decimals
    )


def reproduces(value: float | None, tableau: str | None, fmt: Format | None) -> bool:
    """Whether `value` shows the same as the cell's Tableau export text."""
    d = cells_mod.parse_display(tableau)
    if value is None or d is None:
        return False
    percent = fmt.percent if fmt else d.percent
    # An export that is already a percent is in percent units; others in value units
    exported = d.value / 100 if percent and d.percent else d.value
    return shows_same(value, exported, tableau, fmt)


def _applies(probe: Probe, cell: Cell, cut) -> bool:
    if cell.measure != probe.measure or cell.verdict not in JUDGED:
        return False
    if probe.param is None:
        return not cut.params
    caption, value = probe.param
    return cut.params.get(caption) == value


def _where(checks: Checks, cut, cell: Cell) -> str:
    preds = []
    for caption, label in cells_mod._cut_filters(checks, cut, {}).items():
        fm = checks.filters.get(caption)
        if fm is None:
            raise cells_mod.MappingGap(caption)
        preds.append(cells_mod._pred(fm, label, "t", prefix=""))
    for header, label in cell.dims.items():
        fm = checks.sheets[cell.sheet].dims[header]
        preds.append(cells_mod._pred(fm, label, "t", prefix=""))
    return " and ".join(p for p in preds if p) or "true"


def _value(ws, sql: str) -> float | None:
    rows = ws.query(sql)
    if not rows or rows[0][0] is None:
        return None
    return float(rows[0][0])


def _run_cell(ws, checks, probe, cell, cut, extract) -> ProbeCell:
    out = ProbeCell(cell.cut, cell.sheet, cell.dims, None, None, False, False)
    try:
        where = _where(checks, cut, cell)

        def fill(sql: str) -> str:
            return sql.replace("{extract}", extract).replace("{where}", where)

        out.dashboard = _value(ws, fill(probe.dashboard))
        out.candidate = _value(ws, fill(probe.candidate))
    except Exception as e:  # noqa: BLE001 - a probe's SQL is analyst-written
        out.error = str(e)
        return out
    out.reproduces = reproduces(out.dashboard, cell.tableau, cell.fmt)
    if cell.cube is not None:
        out.candidate_matches_cube = shows_same(
            out.candidate, cell.cube * cell.scale, cell.tableau, cell.fmt
        )
    return out


def run(ws, checks: Checks, cells: list[Cell], extract: str = TAB) -> list[ProbeResult]:
    """Run every probe over the judged cells it applies to.

    Args:
        ws: The analysis workspace with the extract attached.
        checks: The dashboard's checks file.
        cells: The judged cells.
        extract: The extract table `{extract}` stands for.

    Returns:
        One result per probe; `proven` needs at least one cell and every cell to
        reproduce the dashboard's number. A probe's SQL error lands in its
        cell's `error`.
    """
    cuts = {c.id: c for c in checks.cuts}
    results = []
    for probe in checks.probes:
        done = [
            _run_cell(ws, checks, probe, c, cuts[c.cut], extract)
            for c in cells
            if c.cut in cuts and _applies(probe, c, cuts[c.cut])
        ]
        results.append(
            ProbeResult(probe.id, bool(done) and all(p.reproduces for p in done), done)
        )
    return results
