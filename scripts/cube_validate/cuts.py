"""Draft a dashboard's cut list: 1 cut per piece of dashboard logic."""

from __future__ import annotations

import yaml

from .snapshot import slug
from .workbook import Workbook


def _non_default(values: list[str], defaults: tuple[str, ...]) -> str | None:
    return next((v for v in values if v not in defaults), None)


def draft_cuts(
    wb: Workbook, dashboards: list[str], values: dict[str, list[str]]
) -> list[dict]:
    """The default view, each card at 1 other value, each parameter value, each click.

    Args:
        wb: The parsed workbook.
        dashboards: The dashboard tabs in scope.
        values: Each card caption's distinct extract values, sorted.

    Returns:
        Cut dicts in the checks-file shape, default first.
    """
    out: list[dict] = [{"id": "default"}]
    seen: set[str] = set()
    for f in wb.filters:
        if f.dashboard not in dashboards or f.caption in seen:
            continue
        seen.add(f.caption)
        pool = list(f.values) or values.get(f.caption, [])
        v = _non_default(pool, f.default_values)
        if v is not None:
            out.append({"id": f"filter-{slug(f.caption)}", "filters": {f.caption: v}})
    for p in wb.params:
        if p.dashboard not in dashboards:
            continue
        for v in p.values:
            if v != p.default:
                out.append(
                    {
                        "id": f"param-{slug(p.caption)}-{slug(v)}",
                        "params": {p.caption: v},
                    }
                )
    for a in wb.actions:
        if a.dashboard in dashboards and a.kind == "filter":
            out.append(
                {
                    "id": f"click-{slug(a.source_sheet)}",
                    "click": {"source_sheet": a.source_sheet, "mark": "largest"},
                }
            )
    return out


def plan_yaml(
    wb: Workbook,
    dashboards: list[str],
    columns: list[str],
    values: dict[str, list[str]],
) -> str:
    """The draft the analyst edits into the checks file: sheets, columns, cuts."""
    sheets = {s: {} for d in dashboards for s in wb.dashboards.get(d, [])}
    draft = {
        "sheets": sheets,
        "extract_columns": columns,
        "filter_cards": sorted(
            {f.caption for f in wb.filters if f.dashboard in dashboards}
        ),
        "params": sorted({p.caption for p in wb.params if p.dashboard in dashboards}),
        "cuts": draft_cuts(wb, dashboards, values),
    }
    return yaml.safe_dump(draft, sort_keys=False, allow_unicode=True)
