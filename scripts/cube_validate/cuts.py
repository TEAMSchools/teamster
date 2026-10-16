"""Draft a dashboard's cut list: 1 cut per piece of dashboard logic."""

from __future__ import annotations

import yaml

from .snapshot import slug
from .workbook import Workbook

ALL = "(All)"


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
    datasources: list[str] | None = None,
) -> str:
    """The draft the analyst edits into the checks file: sheets, columns, cuts.

    Args:
        wb: The parsed workbook.
        dashboards: The dashboard tabs in scope.
        columns: The chosen extract's columns.
        values: Each card caption's distinct extract values.
        datasources: Every embedded extract's caption, so the analyst can name
            the one to compare.

    Returns:
        The draft as YAML, led by every dashboard and extract the workbook holds.
    """
    sheets = {s: {} for d in dashboards for s in wb.dashboards.get(d, [])}
    defaults: dict[str, str | list[str]] = {}
    for f in wb.filters:
        if f.dashboard in dashboards and f.caption not in defaults:
            shown = list(f.default_values)
            defaults[f.caption] = (
                ALL
                if f.default_all or not shown
                else shown[0]
                if len(shown) == 1
                else shown
            )
    draft = {
        "dashboards": list(wb.dashboards),
        "datasources": list(datasources or []),
        "sheets": sheets,
        "extract_columns": columns,
        "filter_cards": sorted(defaults),
        # what each card shows before anyone touches it; copy the single-valued
        # ones into the checks file's defaults
        "filter_card_defaults": dict(sorted(defaults.items())),
        "params": sorted({p.caption for p in wb.params if p.dashboard in dashboards}),
        "cuts": draft_cuts(wb, dashboards, values),
    }
    return yaml.safe_dump(draft, sort_keys=False, allow_unicode=True)
