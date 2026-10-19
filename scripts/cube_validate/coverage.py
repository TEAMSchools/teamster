"""Coverage: one line per must-cover measure, saying whether Cube was really tested."""

from __future__ import annotations

from collections import Counter

from . import workbook
from .cells import COINCIDENTAL, DECIDED, FORMULA_GAP, NEVER_CUBE, PASS, ROW_GAP
from .config import Checks, param_matches
from .report import small

STATUSES = (
    "gaps open",
    "covered",
    "in the data, not in Cube",
    "not judged",
    "not mapped yet",
    "only on sheets with names",
    "not on these dashboards",
)
_OPEN = (ROW_GAP, FORMULA_GAP, COINCIDENTAL)
_JUDGED = (PASS, *_OPEN, *DECIDED)


def _showing(twb_text: str, checks: Checks, caption: str) -> list[str]:
    """Sheets of this run's dashboards that show the caption."""
    if not twb_text:
        return []
    wb = workbook.read_workbook(twb_text)
    on_dashboards = {s for d in checks.dashboards for s in wb.dashboards.get(d, [])}
    return [s for s in workbook.sheets_showing(twb_text, caption) if s in on_dashboards]


def _status(entry, mine: list, checks: Checks, rows_result, twb_text: str):
    judged = [c for c in mine if c.verdict in _JUDGED]
    gaps = [c for c in judged if c.verdict in _OPEN]
    if gaps:
        return "gaps open", f"{small(len(judged))} judged, {small(len(gaps))} gaps"
    if entry.cube is not None and judged:
        return "covered", f"{small(len(judged))} judged cells"
    if entry.cube is None:
        differing = sum(rows_result.differing_columns.get(r, 0) for r in entry.rows)
        if not differing:
            return "in the data, not in Cube", "rows agree"
        return "in the data, not in Cube", f"{small(differing)} rows differ"
    if mine and all(c.verdict in NEVER_CUBE for c in mine):
        reason = Counter(c.reason or c.verdict for c in mine).most_common(1)[0][0]
        return "not judged", reason
    caption = workbook.measure_caption(twb_text, entry.column) if twb_text else ""
    shown = _showing(twb_text, checks, caption) if twb_text else []
    unmapped = [
        s for s in shown if s not in checks.sheets and s not in checks.excluded_sheets
    ]
    if unmapped:
        return "not mapped yet", ", ".join(unmapped)
    if shown and all(s in checks.excluded_sheets for s in shown):
        return "only on sheets with names", "; ".join(
            f"{s}: {checks.excluded_sheets[s]}" for s in shown
        )
    if shown:
        return "not judged", "mapped, but no cell was built"
    return "not on these dashboards", ""


def lines(checks: Checks, cells: list, rows_result, twb_text: str) -> list[dict]:
    """One coverage line per must-cover entry.

    Args:
        checks: The checks file, with its must-cover list.
        cells: The cells after decisions are applied.
        rows_result: The row reconciliation, for the rows behind a measure.
        twb_text: The workbook XML, empty when none was captured.

    Returns:
        One dict per entry: name, status, detail, source.
    """
    params = {c.id: c.params for c in checks.cuts}
    out = []
    for e in checks.must_cover:
        mine = [
            c
            for c in cells
            if c.measure == e.column
            and c.cut in params
            and param_matches(e.param, params[c.cut])
        ]
        status, detail = _status(e, mine, checks, rows_result, twb_text)
        out.append(
            {"name": e.name, "status": status, "detail": detail, "source": e.source}
        )
    return out
