"""`rebuild-sheet`: rebuild a sheet in SQL and match it to the sheet's export,
and the workbook check `compare` runs against each rebuild check."""

from __future__ import annotations

import dataclasses
import json
import re

# trunk-ignore(bandit/B405): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import tableauserverclient as TSC

from . import find_field as finder
from . import read_sheet, tableau
from .bq import Warehouse
from .config import (
    Comparison,
    ConfigError,
    ViewConfig,
    find_comparison,
    write_rebuild_check,
)
from .cube_client import Cube
from .moment import WINDOW
from .pipeline import (
    Refusal,
    cell_query,
    checked_as_of,
    comparison_cuts,
    cut_label,
    row_query,
    sheet_query,
    sheet_query_fingerprint,
    unique,
)

# A rebuild's sheet query is time-travelled to the refresh; keep a margin inside
# 7 days.
REBUILD_WINDOW = WINDOW - timedelta(hours=1)


def _require(comparison: Comparison, *keys: str) -> None:
    missing = [k for k in keys if getattr(comparison, k) in (None, "")]
    if missing:
        raise Refusal(f"comparison {comparison.id!r} has no {', '.join(missing)}")


def reshape_text(
    shelves: dict[str, Any], reshaped: tableau.Reshaped | None = None
) -> str:
    """`dropped A; added C to rows, D to columns; cleared the filters on E`,
    for a `shelves:` key. With the `reshaped` copy, also the table calcs the
    drop removed and the kept ones that recompute along a changed shelf.
    """
    parts = []
    if shelves.get("drop"):
        parts.append(f"dropped {', '.join(shelves['drop'])}")
    added = [
        f"{', '.join(captions)} to {tableau.SHELF_NAMES[shelf]}"
        for shelf, captions in shelves.get("add", {}).items()
    ]
    if added:
        parts.append(f"added {', '.join(added)}")
    if shelves.get("clear_filters"):
        parts.append(f"cleared the filters on {', '.join(shelves['clear_filters'])}")
    if reshaped is not None:
        if reshaped.removed:
            parts.append(f"removed the table calcs {', '.join(reshaped.removed)}")
        parts += [
            f"recomputes along the new {shelf}: {', '.join(captions)}"
            for shelf, captions in reshaped.recomputed.items()
        ]
    return "; ".join(parts)


def _query_members(query: dict) -> Iterator[str]:
    """Every member a Cube query names, nested `and`/`or` filters included."""
    yield from query.get("measures", [])
    yield from query.get("dimensions", [])
    yield from (t["dimension"] for t in query.get("timeDimensions", []))
    stack = list(query.get("filters", []))
    while stack:
        f = stack.pop()
        if "member" in f:
            yield f["member"]
        stack += f.get("and", []) + f.get("or", [])


def missing_members(
    cfg: ViewConfig, comparisons: Iterable[Comparison], meta: dict
) -> list[str]:
    """The members `compare` would query that Cube's `/meta` lacks, as `<id>: <member>`.

    Read from the queries `compare` sends, so a mapping to a member the model
    dropped or renamed is caught before anything is priced. `/meta` lists what
    this viewer may query: Cube refuses a load of any member it hides.
    """
    known = {
        m["name"]
        for cube in meta.get("cubes", [])
        for kind in ("measures", "dimensions", "segments")
        for m in cube.get(kind) or []
    }
    found: list[str] = []
    for comparison in comparisons:
        queries = [
            cell_query(cfg.view, comparison, cut) for cut in comparison_cuts(comparison)
        ]
        if comparison.rows is not None:
            queries.append(row_query(cfg.view, comparison))
        names = unique(m for q in queries for m in _query_members(q))
        found += [f"{comparison.id}: {m}" for m in names if m not in known]
    return found


# How `workbook_check` starts a line for a workbook Tableau would not answer for.
TABLEAU_ANSWERED = "Tableau answered"


def _sheet_columns(twb_xml: str, sheet: str) -> list[ET.Element]:
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    ws = next((w for w in root.iter("worksheet") if w.get("name") == sheet), None)
    if ws is None:
        raise Refusal(f"the workbook has no worksheet {sheet!r}")
    return [
        col
        for deps in ws.iter("datasource-dependencies")
        for col in deps.findall("column")
    ]


def _bare(name: str) -> str:
    return name[1:-1] if name.startswith("[") and name.endswith("]") else name


def _export_columns(
    comparison: Comparison,
    headers: list[str],
    columns: list[ET.Element],
) -> tuple[dict[str, str], str]:
    """Map export headers to dashboard dim names, and pick the value header."""
    lower = {h.lower(): h for h in headers}
    mapping: dict[str, str] = {}
    for dim in comparison.dims:
        names = {dim.dashboard}
        names |= {
            caption
            for caption, pair in comparison.filters.items()
            if pair.dashboard == dim.dashboard
        }
        names |= {
            col.get("caption") or ""
            for col in columns
            if _bare(col.get("name") or "") == dim.dashboard
        }
        found = [lower[n.lower()] for n in names if n and n.lower() in lower]
        if not found:
            raise Refusal(
                f"no export column for dim {dim.dashboard!r}; "
                f"the export has {', '.join(headers)}"
            )
        mapping[found[0]] = dim.dashboard
    rest = [h for h in headers if h not in mapping]
    field = comparison.sheet_field
    if field:
        if field not in rest:
            raise Refusal(
                f"sheet_field {field!r} is not an export column; "
                f"the export has {', '.join(rest)}"
            )
        return mapping, field
    if len(rest) != 1:
        raise Refusal(
            f"the export has {len(rest)} columns besides the dims "
            f"({', '.join(rest)}); name the one to compare with sheet_field"
        )
    return mapping, rest[0]


MEASURE_NAMES, MEASURE_VALUES = "Measure Names", "Measure Values"


def long_to_wide(rows: list[dict[str, str]], field: str | None) -> list[dict[str, str]]:
    """Keep one field of a long export as its own column.

    A sheet with `Measure Names` on a shelf exports one row per field, naming
    it in `Measure Names` and holding it in `Measure Values`. `field` names
    one of those fields, or a column beside them (a measure on another shelf),
    which repeats on every field's row of a mark, so each mark is kept once. A
    wide export comes back as is.

    Raises:
        Refusal: The export is long and `field` is unset or names neither a
            field nor a column in it; the message lists both.
    """
    if not rows or MEASURE_NAMES not in rows[0]:
        return rows
    names = sorted({r[MEASURE_NAMES] for r in rows})
    others = [h for h in rows[0] if h not in (MEASURE_NAMES, MEASURE_VALUES)]
    choices = f"its fields are {', '.join(names)}; its columns are {', '.join(others)}"
    if not field:
        raise Refusal(f"the export has one row per field; set sheet_field ({choices})")
    if field in names:
        return [
            {**{k: r[k] for k in others}, field: r[MEASURE_VALUES]}
            for r in rows
            if r[MEASURE_NAMES] == field
        ]
    if field in others:
        marks = dict.fromkeys(tuple((k, r[k]) for k in others) for r in rows)
        return [dict(mark) for mark in marks]
    raise Refusal(f"sheet_field {field!r} is not in the export; {choices}")


@dataclasses.dataclass(frozen=True)
class SheetGaps:
    """Sheet fields with no Cube member, by caption. Values are never read."""

    cuts: list[str]
    filters: list[str]
    restricting: list[str]
    # Caption to why the field needs no Cube member: `copy of <mapped caption>`
    # or `display switch on <parameter caption>`.
    notes: dict[str, str] = dataclasses.field(default_factory=dict)
    # Caption to the datasource column, for a plain field (never a calculation).
    columns: dict[str, str] = dataclasses.field(default_factory=dict)


_WHOLE_REF = re.compile(r"\[(?P<name>[^\]]+)\]")
_PARAMETER_REF = re.compile(r"\[Parameters\]\.\[(?P<name>[^\]]+)\]")
_STRING_LITERAL = re.compile(r"'[^']*'|\"[^\"]*\"")
_FIELD_REF = re.compile(r"\[[^\]]+\]")
_COMMENT = re.compile(r"//[^\n]*")


def _parameter_only(formula: str) -> re.Match | None:
    """The first parameter a formula reads, when it reads no other field.

    Comments go before string literals, so an apostrophe in a comment cannot
    pair with one on a later line and hide the field between them.
    """
    bare = _STRING_LITERAL.sub("", _COMMENT.sub("", formula))
    if _FIELD_REF.search(_PARAMETER_REF.sub("", bare)):
        return None
    return _PARAMETER_REF.search(bare)


def _parameter_captions(twb_xml: str) -> dict[str, str]:
    """Map each parameter's bare name to its caption."""
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    return {
        (col.get("name") or "").strip("[]"): col.get("caption") or ""
        for ds in root.iter("datasource")
        if ds.get("name") == "Parameters"
        for col in ds.findall("column")
    }


def sheet_gaps(twb_xml: str, comparison: Comparison) -> SheetGaps:
    """Name the sheet's cuts and filters that have no Cube member.

    A field counts as having one when the comparison maps it anywhere: a dim,
    a filter, or a row grain or value. Aggregated fields, `Measure Names`,
    user filters and fields built on the viewer's identity are skipped.

    Also returns `notes` (a plain copy of a mapped field, or a calculation that
    reads only parameters) and `columns` (the datasource column behind each
    plain missing field).
    """
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    ws = finder.worksheet(ET.fromstring(twb_xml), comparison.sheet or "")
    if ws is None:
        raise Refusal(f"the workbook has no worksheet {comparison.sheet!r}")
    pairs = [*comparison.dims, *comparison.filters.values()]
    if comparison.rows:
        pairs += [*comparison.rows.grain, *comparison.rows.values]
    mapped = {p.dashboard for p in pairs}
    mapped_captions = set(comparison.filters)
    caption, personal = finder.sheet_fields(ws)
    groups = finder.group_fields(ws)
    mapped_caption_of = {p.dashboard: c for c, p in comparison.filters.items()}

    def field_of(ref: str) -> str | None:
        name = finder.filter_field(ref, groups)
        if name is None:
            return None
        if name in mapped or name in personal or caption.get(name) in mapped_captions:
            return None
        return name

    shelves = " ".join(
        [el.text or "" for el in ws.iter() if el.tag in ("rows", "cols")]
        + [el.get("column") or "" for enc in ws.iter("encodings") for el in enc]
    )
    cuts = {f for ref in finder.FIELD_REF.finditer(shelves) if (f := field_of(ref[0]))}
    filters: set[str] = set()
    restricting: set[str] = set()
    for filter_el in ws.iter("filter"):
        name = field_of(filter_el.get("column") or "")
        if name is None or name in cuts:
            continue
        filters.add(name)
        if finder.restricts(filter_el):
            restricting.add(name)

    def captions(names: set[str]) -> list[str]:
        return sorted({caption.get(n, n) for n in names})

    calcs = {c.name.strip("[]"): c.formula for c in finder.calculated_fields(twb_xml)}
    parameters = _parameter_captions(twb_xml)
    notes: dict[str, str] = {}
    columns: dict[str, str] = {}
    for name in cuts | filters:
        formula = (calcs.get(name) or "").strip()
        # A group or bin is no datasource column: triage cannot value-check it.
        if name not in calcs and name not in groups:
            columns[caption.get(name, name)] = name
        elif (param := _parameter_only(formula)) is not None:
            notes[caption.get(name, name)] = (
                f"display switch on {parameters.get(param['name']) or param['name']}"
            )
        elif (whole := _WHOLE_REF.fullmatch(formula)) is not None:
            ref = whole["name"]
            if ref in mapped or caption.get(ref) in mapped_captions:
                shown = mapped_caption_of.get(ref) or caption.get(ref, ref)
                notes[caption.get(name, name)] = f"copy of {shown}"

    return SheetGaps(
        captions(cuts), captions(filters), captions(restricting), notes, columns
    )


TOTAL_LABELS = ("All", "*")


def _alias_keys(columns: list[ET.Element], dim: str) -> dict[str, str]:
    """Map each alias a sheet displays for a dim back to the stored value.

    A string key is stored quoted (`"Camden"`); the quotes are dropped.
    """
    out: dict[str, str] = {}
    for col in columns:
        if _bare(col.get("name") or "") != dim:
            continue
        for alias in col.iter("alias"):
            key, shown = alias.get("key") or "", alias.get("value") or ""
            if len(key) > 1 and key[0] == key[-1] == '"':
                key = key[1:-1]
            out[shown] = key
    return out


def _shelf_dims(
    comparison: Comparison, shaped: str, sheet: str, columns: list[ET.Element]
) -> set[str]:
    """The comparison's dims that sit on the sheet's rows or columns shelf.

    A dim matches by its dashboard name, a column caption or a `filters`
    caption. A dim off the shelves is a detail field, whose `*` is a real
    value.
    """
    shape = finder.sheet_shape(shaped, sheet)
    shelved = {n.lower() for n in [*shape.rows, *shape.cols]}
    out: set[str] = set()
    for dim in comparison.dims:
        names = {dim.dashboard}
        names |= {
            caption
            for caption, pair in comparison.filters.items()
            if pair.dashboard == dim.dashboard
        }
        names |= {
            col.get("caption") or ""
            for col in columns
            if _bare(col.get("name") or "") == dim.dashboard
        }
        if any(n and n.lower() in shelved for n in names):
            out.add(dim.dashboard)
    return out


def _ignored_headers(
    headers: list[str],
    mapping: dict[str, str],
    value: str,
    columns: list[ET.Element],
    calcs: list[tableau.TableCalc],
) -> set[str]:
    """Export headers that name a measure or table calc other than the
    compared value.

    A dual axis repeats a row once per pane, and the panes differ only in such
    a column.
    """
    names = {
        read_sheet._export_name(n)
        for col in columns
        if col.get("role") == "measure"
        for n in (col.get("caption") or "", _bare(col.get("name") or ""))
        if n
    }
    names |= {read_sheet._export_name(c.caption) for c in calcs}
    return {
        h
        for h in headers
        if h not in mapping and h != value and read_sheet._export_name(h) in names
    }


def _export_cells(
    comparison: Comparison,
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    value: str,
    columns: list[ET.Element],
    probe_rows: list[dict],
    *,
    shelf_dims: set[str],
    ignored: set[str],
) -> tuple[list[dict], int, int]:
    """Turn export rows into sheet-query-shaped cells; count total and summed rows.

    An export shows a dim's alias (grade 0 as `K`), so each value goes back
    through the sheet's aliases. A sheet with totals exports them as rows whose
    dim reads `All`, or `*` for a dim in `shelf_dims`; those are dropped,
    unless the sheet query has a real member with that label for that dim. A
    dual axis repeats a row once per pane, so rows that match in every column
    but `ignored` count once. With `split_rows: sum`, every row is kept, and
    rows that share every mapped dim (split by a sheet field Cube lacks) are
    added into one cell; blanks are skipped, and a cell of blanks stays blank.
    """
    aliases = {d.dashboard: _alias_keys(columns, d.dashboard) for d in comparison.dims}
    real = {
        (d.dashboard, label)
        for d in comparison.dims
        for label in TOTAL_LABELS
        if any(str(r[d.dashboard]) == label for r in probe_rows)
    }
    cells: list[dict] = []
    totals = 0
    seen: set[tuple] = set()
    for r in rows:
        whole = tuple(sorted((k, str(v)) for k, v in r.items() if k not in ignored))
        if whole in seen and comparison.split_rows != "sum":
            continue
        seen.add(whole)
        dims = {d: r[h] for h, d in mapping.items()}
        if any(
            (v == "All" or (v == "*" and d in shelf_dims)) and (d, v) not in real
            for d, v in dims.items()
        ):
            totals += 1
            continue
        dims = {d: aliases[d].get(v, v) for d, v in dims.items()}
        cells.append({**dims, "value": r[value]})
    if comparison.split_rows != "sum":
        return cells, totals, 0
    merged: dict[tuple, dict] = {}
    sums: dict[tuple, Decimal | None] = {}
    for cell in cells:
        key = tuple(cell[d.dashboard] for d in comparison.dims)
        merged.setdefault(key, cell)
        text = str(cell["value"]).strip()
        if not text:
            sums.setdefault(key, None)
            continue
        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise Refusal(f"cannot add export value {text!r}") from exc
        sums[key] = (sums.get(key) or Decimal(0)) + number
    out = []
    for k, cell in merged.items():
        total = sums[k]
        out.append(
            {**cell, "value": "" if total is None else format(total.normalize(), "f")}
        )
    return out, totals, len(cells) - len(out)


def _comparison_by_id(cfg: ViewConfig, path: Path, comparison_id: str) -> Comparison:
    comparison = next((c for c in cfg.comparisons if c.id == comparison_id), None)
    if comparison is None:
        raise Refusal(f"{path}: no comparison {comparison_id!r}")
    return comparison


def _capture(
    comparison: Comparison,
    tbl: tableau.Tableau,
    captures: dict[tuple, tableau.Snapshot] | None,
) -> tuple[str, str, list[ET.Element], list[dict], list[dict], tableau.Snapshot]:
    """Export a comparison's sheet once per workbook, sheet, cuts, parameter
    values and reshape.

    Returns:
        The workbook XML, the same with the sheet reshaped (`shelves`), the
        reshaped sheet's columns, the cuts a REST export takes, the cuts only
        a browser can check, and the snapshot.
    """
    _require(comparison, "workbook", "sheet")
    workbook, sheet = comparison.workbook or "", comparison.sheet or ""
    twb = tbl.download_twb(workbook)
    if not comparison.unpublished and sheet not in tableau.published_sheets(twb):
        raise Refusal(
            f"comparison {comparison.id!r}: sheet {sheet!r} is "
            f"{tableau.NOT_PUBLISHED}; set unpublished: true to compare it anyway"
        )
    parameters, shelves = comparison.parameters, comparison.shelves
    try:
        if parameters:
            tableau.set_parameters(twb, parameters)
        shaped = tableau.set_shelves(twb, sheet, shelves).xml if shelves else twb
    except ValueError as exc:
        raise Refusal(f"comparison {comparison.id!r}: {exc}") from exc
    if why := read_sheet.text_measure(
        read_sheet.read_sheet(shaped, sheet), comparison.sheet_field
    ):
        raise Refusal(f"comparison {comparison.id!r}: {why}")
    columns = _sheet_columns(shaped, sheet)
    measures = [c.get("name") or "" for c in columns if c.get("role") == "measure"]
    if not measures:
        raise Refusal(f"sheet {sheet!r} lists no measure")
    exportable, browser = tableau.split_cuts(comparison_cuts(comparison), twb)
    if not exportable:
        raise Refusal(f"comparison {comparison.id!r} has no cut a REST export can take")
    captures = {} if captures is None else captures

    def edit(x: str) -> str:
        # The reshape goes first, so the format drop sees any column it copied.
        x = tableau.set_shelves(x, sheet, shelves).xml if shelves else x
        x = tableau.expose_sheet(tableau.drop_number_formats(x, measures), sheet)
        # A field shown only behind a parameter value exports once the copy
        # carries that value.
        return tableau.set_parameters(x, parameters) if parameters else x

    key = (
        workbook,
        sheet,
        tuple(cut_label(cut) for cut in exportable),
        tuple(sorted(parameters.items())),
        json.dumps(shelves, sort_keys=True),
    )
    if key not in captures:
        try:
            captures[key] = tbl.capture(workbook, sheet, exportable, edit)
        except (LookupError, tableau.RefreshMovedError) as exc:
            raise Refusal(f"cannot export {sheet!r}: {exc}") from exc
    return twb, shaped, columns, exportable, browser, captures[key]


def rebuild_sheet_headers(
    cfg: ViewConfig,
    path: Path,
    comparison_id: str,
    *,
    tbl: tableau.Tableau,
    captures: dict[tuple, tableau.Snapshot] | None = None,
) -> None:
    """Print each exported cut's column headers, and the fields a long export
    names, without probing or writing anything. A reshaped comparison first
    prints the copy's rows and columns.
    """
    comparison = _comparison_by_id(cfg, path, comparison_id)
    twb, shaped, _, exportable, _, snap = _capture(comparison, tbl, captures)
    if comparison.shelves:
        sheet = comparison.sheet or ""
        shape = finder.sheet_shape(shaped, sheet)
        reshaped = tableau.set_shelves(twb, sheet, comparison.shelves)
        calcs = reshape_text({}, reshaped)
        print(
            f"{comparison.id} reshaped: rows {', '.join(shape.rows) or 'none'}; "
            f"columns {', '.join(shape.cols) or 'none'}"
            + (f"; {calcs}" if calcs else "")
        )
    for cut, rows in zip(exportable, snap.exports, strict=True):
        headers = list(rows[0]) if rows else []
        print(
            f"{comparison.id} cut {cut_label(cut)}: {', '.join(headers) or 'no rows'}"
        )
        if MEASURE_NAMES in headers:
            names = sorted({r[MEASURE_NAMES] for r in rows})
            print(f"  {MEASURE_NAMES}: {', '.join(names)}")


def rebuild_sheet(
    cfg: ViewConfig,
    path: Path,
    comparison_id: str,
    *,
    wh: Warehouse,
    tbl: tableau.Tableau,
    now: datetime,
    max_usd: float,
    captures: dict[tuple, tableau.Snapshot] | None = None,
    failures_dir: Path | None = None,
) -> tableau.RebuildResult:
    """Rebuild a comparison's sheet in SQL, match it to the sheet's export, and
    write `rebuild_check:`.

    Failures and browser cuts print to the terminal only: a count per reason
    and a few samples, with the full list in `failures_dir` when given.
    `captures` keeps each sheet's export across calls, so comparisons on one
    sheet and cuts share a capture.

    Raises:
        Refusal: The comparison is unknown or incomplete, an exportable cut
            has no rows on a side, or the cells did not match.
    """
    comparison = _comparison_by_id(cfg, path, comparison_id)
    _require(comparison, "workbook", "sheet", "dashboard_view", "decimals")
    try:
        find_comparison(path, comparison.id)
    except ConfigError as exc:
        raise Refusal(str(exc)) from exc
    twb, shaped, columns, exportable, browser, snap = _capture(
        comparison, tbl, captures
    )
    if snap.refresh_started < now - REBUILD_WINDOW:
        raise Refusal(
            f"the extract refreshed at {snap.refresh_started}, outside the 7 days "
            "of warehouse history; rebuild after the next refresh"
        )

    sheet = comparison.sheet or ""
    shelf_dims = _shelf_dims(comparison, shaped, sheet, columns)
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    ws = finder.worksheet(ET.fromstring(shaped), sheet)
    calcs = tableau.table_calcs(ws) if ws is not None else []
    exports: list[dict] = []
    probes: list[dict] = []
    totals_skipped = 0
    with wh.budget(max_usd):
        for cut, rows in zip(exportable, snap.exports, strict=True):
            label = cut_label(cut)
            probe_rows = wh.rows(
                checked_as_of(
                    sheet_query(cfg, comparison, cut), snap.refresh_started, wh
                ).sql
            )
            if not rows or not probe_rows:
                side = "export" if not rows else "sheet query"
                raise Refusal(f"cut {label}: the {side} has no rows")
            rows = long_to_wide(rows, comparison.sheet_field)
            mapping, value = _export_columns(comparison, list(rows[0]), columns)
            cells, totals, summed = _export_cells(
                comparison,
                rows,
                mapping,
                value,
                columns,
                probe_rows,
                shelf_dims=shelf_dims,
                ignored=_ignored_headers(list(rows[0]), mapping, value, columns, calcs),
            )
            if totals:
                print(
                    f"cut {label}: skipped {totals} total rows "
                    f"({', '.join(TOTAL_LABELS)})"
                )
            if summed:
                print(f"cut {label}: summed {summed} split export rows into others")
            totals_skipped += totals
            exports += [{**c, "cut": label} for c in cells]
            probes += [
                {
                    **{d.dashboard: r[d.dashboard] for d in comparison.dims},
                    "value": r["value"],
                    "cut": label,
                }
                for r in probe_rows
            ]

    try:
        proof = tableau.match_export(comparison, exports, probes, twb_xml=twb, now=now)
    except ValueError as exc:
        raise Refusal(f"comparison {comparison.id!r}: {exc}") from exc
    if proof.blanks_skipped:
        print(
            f"Skipped {proof.blanks_skipped} blank cells "
            "(blank in the export, NULL in the sheet query)"
        )
    for cut in browser:
        print(f"Check in the browser: {cut_label(cut)}")
    if not proof.matched:
        print(
            f"Rebuild check failed for {comparison.id} ({proof.cells} cells matched):"
        )
        _print_failures(comparison.id, proof.failures, failures_dir)
        raise Refusal(f"comparison {comparison.id!r} did not match; nothing written")

    # The copy's shelves: a dropped field is no longer a missing cut.
    gaps = sheet_gaps(shaped, comparison)
    for kind, names in (("cuts", gaps.cuts), ("filters", gaps.filters)):
        if names:
            print(f"Sheet {kind} with no Cube member: {', '.join(names)}")

    write_rebuild_check(
        path,
        comparison.id,
        {
            "fingerprint": proof.fingerprint,
            "cells": proof.cells,
            "matched_at": proof.matched_at.isoformat(),
            "workbook_updated_at": tbl.workbook_updated(
                comparison.workbook or ""
            ).isoformat(),
            "sheet_query_fingerprint": sheet_query_fingerprint(cfg, comparison),
            # `workbook_check` reads a republish that changed neither this nor
            # `fingerprint` as no change to the sheet.
            "source_fingerprint": tableau.source_fingerprint(
                twb, comparison.sheet or ""
            ),
            # False only for a comparison set `unpublished: true`; `_capture`
            # refuses any other unpublished sheet.
            "published": sheet in tableau.published_sheets(twb),
            # `compare` lists every other cut as one to check in the browser.
            "cuts": [cut_label(cut) for cut in exportable],
            # `compare` lists these rows as totals no rebuild check covered.
            "totals_skipped": totals_skipped,
            # The parameter values the copy showed; the fingerprint covers them.
            **(
                {"parameters": dict(comparison.parameters)}
                if comparison.parameters
                else {}
            ),
            # The reshape the copy carried; `compare` names it, since the check
            # covers the reshaped grain, not the sheet's own.
            **({"shelves": comparison.shelves} if comparison.shelves else {}),
            # `compare` lists these as missing cuts and filters to sort.
            "missing_cuts": gaps.cuts,
            "missing_filters": gaps.filters,
            "restricting_filters": gaps.restricting,
            # `sort` reads these offline: a copy or display switch needs no
            # member; a plain column can be value-checked.
            "filter_notes": gaps.notes,
            "missing_columns": gaps.columns,
        },
    )
    print(
        f"Matched {comparison.id}: {proof.cells} cells; wrote rebuild_check to {path}."
    )
    return proof


FAILURE_SAMPLES = 5


def _failure_reason(failure: str) -> str:
    if " decimals (" in failure:
        return "value differs at the displayed decimals"
    return failure.rsplit(": ", 1)[-1]


def _print_failures(
    comparison_id: str, failures: list[str], failures_dir: Path | None
) -> None:
    """Print a count per reason and a few samples; save the full list locally.

    A failure line can name a student, so the full list stays in the local
    cache, never in anything posted.
    """
    for reason, n in Counter(map(_failure_reason, failures)).most_common():
        print(f"  {n} x {reason}")
    print(f"  First {min(FAILURE_SAMPLES, len(failures))} of {len(failures)}:")
    for failure in failures[:FAILURE_SAMPLES]:
        print(f"    {failure}")
    if failures_dir is not None:
        failures_dir.mkdir(parents=True, exist_ok=True)
        path = failures_dir / f"rebuild-failures-{comparison_id}.txt"
        path.write_text("\n".join(failures) + "\n")
        print(f"  Full list: {path}")


class WorkbookCache:
    """Each workbook's publish time and file, asked of Tableau once.

    Share one across `workbook_check` and `unpublished_sheets` so a compare
    run downloads a republished workbook once. A Tableau error is kept as
    well, so later comparisons on that workbook read it without asking again.
    """

    def __init__(self, tbl: tableau.Tableau) -> None:
        self.tbl = tbl
        self._updated: dict[str, datetime | TSC.ServerResponseError] = {}
        self._twbs: dict[str, str | TSC.ServerResponseError] = {}

    def updated(self, luid: str) -> datetime:
        """The workbook's publish time.

        Raises:
            TSC.ServerResponseError: Tableau erred on this workbook, now or
                on an earlier ask.
        """
        if luid not in self._updated:
            try:
                self._updated[luid] = self.tbl.workbook_updated(luid)
            except TSC.ServerResponseError as exc:
                self._updated[luid] = exc
        got = self._updated[luid]
        if isinstance(got, TSC.ServerResponseError):
            raise got
        return got

    def twb(self, luid: str) -> str:
        """The workbook's XML.

        Raises:
            TSC.ServerResponseError: Tableau erred on this workbook's download,
                now or on an earlier ask.
        """
        if luid not in self._twbs:
            try:
                self._twbs[luid] = self.tbl.download_twb(luid)
            except TSC.ServerResponseError as exc:
                self._twbs[luid] = exc
        got = self._twbs[luid]
        if isinstance(got, TSC.ServerResponseError):
            raise got
        return got

    def downloaded(self, luid: str) -> bool:
        """True when the workbook's XML is already in hand."""
        return isinstance(self._twbs.get(luid), str)


def workbook_check(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    *,
    tbl: tableau.Tableau,
    cube: Cube,
    workbooks: WorkbookCache | None = None,
) -> list[str]:
    """List the comparisons whose sheet or Cube members changed since their
    rebuild check.

    A workbook published after the check is downloaded once and its sheet
    compared by what the check covers: `fingerprint` (the sheet's formulas
    and filters) and `source_fingerprint` (its datasources' connection and
    filters). A republish that changed neither is printed as such and not
    listed. A rebuild check without `source_fingerprint` cannot rule out a datasource
    change, so it is stale after any republish. A matched comparison that maps a
    member Cube's `/meta` no longer lists is stale too, and one whose workbook
    Tableau errs on reads `TABLEAU_ANSWERED` and its error.

    Args:
        cfg: The view's config.
        comparisons: The comparisons to check.
        tbl: Tableau, for each workbook's publish time and file.
        cube: Cube, for its `/meta` members.
        workbooks: The run's shared workbook cache; a new one on `tbl` when
            omitted.

    Returns:
        One line per problem, each starting with its comparison's id and
        ending in what to do.
    """
    workbooks = WorkbookCache(tbl) if workbooks is None else workbooks
    proven = [c for c in comparisons if c.rebuild_check is not None]
    stale = [
        f"{line}, which Cube's model no longer has; fix the mapping and re-run "
        "`rebuild-sheet`"
        for line in missing_members(cfg, proven, cube.meta())
    ]
    for comparison in comparisons:
        if not comparison.workbook:
            continue
        proof = comparison.rebuild_check
        if proof is None:
            stale.append(f"{comparison.id}: no rebuild check")
            continue
        try:
            updated = workbooks.updated(comparison.workbook)
            republished = bool(proof.workbook_updated_at) and updated > (
                datetime.fromisoformat(proof.workbook_updated_at or "")
            )
            twb = workbooks.twb(comparison.workbook) if republished else ""
        except TSC.ServerResponseError as exc:
            # One workbook's error is its comparisons' alone.
            stale.append(
                f"{comparison.id}: {TABLEAU_ANSWERED} {exc.code} {exc.summary}; "
                "try again, or re-run `rebuild-sheet` if the workbook moved"
            )
            continue
        if not proof.workbook_updated_at:
            stale.append(
                f"{comparison.id}: rebuild check has no workbook_updated_at; "
                "re-run `rebuild-sheet`"
            )
            continue
        if updated <= datetime.fromisoformat(proof.workbook_updated_at):
            continue
        published = (
            f"workbook published {updated.isoformat()}, after the rebuild check's "
            f"{proof.workbook_updated_at}"
        )
        sheet = comparison.sheet or ""
        try:
            formulas = tableau.formula_fingerprint(twb, sheet)
            sources = tableau.source_fingerprint(twb, sheet)
        except ValueError as exc:
            stale.append(
                f"{comparison.id}: {published}, and {exc}; re-run `rebuild-sheet`"
            )
            continue
        if formulas != proof.fingerprint:
            stale.append(
                f"{comparison.id}: {published}; the sheet's formulas or filters "
                "changed; re-run `rebuild-sheet`"
            )
        elif not proof.source_fingerprint:
            stale.append(
                f"{comparison.id}: {published}; the sheet's formulas are unchanged, "
                "but the rebuild check predates the datasource check; re-run "
                "`rebuild-sheet` once"
            )
        elif sources != proof.source_fingerprint:
            stale.append(
                f"{comparison.id}: {published}; a datasource's connection or "
                "filters changed; re-run `rebuild-sheet`"
            )
        else:
            print(
                f"{comparison.id}: republished {updated.isoformat()}, sheet unchanged"
            )
    return stale


def unpublished_sheets(
    comparisons: list[Comparison],
    *,
    tbl: tableau.Tableau,
    workbooks: WorkbookCache | None = None,
) -> dict[str, str]:
    """Name the comparisons whose sheet no published dashboard shows.

    A comparison with `unpublished: true` or no `sheet` is never listed. A
    workbook is downloaded once, and only when one of its comparisons' check
    does not record that the sheet is published, or the workbook was
    published after the check.

    Args:
        comparisons: The comparisons to check.
        tbl: Tableau, for each workbook's publish time and file.
        workbooks: The run's shared workbook cache; a new one on `tbl` when
            omitted.

    Returns:
        Each such comparison's id and why it is skipped; a workbook Tableau
        errs on reads `TABLEAU_ANSWERED` and its error.
    """
    workbooks = WorkbookCache(tbl) if workbooks is None else workbooks
    skipped: dict[str, str] = {}
    for comparison in comparisons:
        proof = comparison.rebuild_check
        if (
            comparison.unpublished
            or not comparison.workbook
            or not comparison.sheet
            or proof is None
        ):
            continue
        luid = comparison.workbook
        try:
            if not workbooks.downloaded(luid):
                at = proof.workbook_updated_at
                if (
                    proof.published is True
                    and at
                    and workbooks.updated(luid) <= datetime.fromisoformat(at)
                ):
                    continue
            twb = workbooks.twb(luid)
        except TSC.ServerResponseError as exc:
            skipped[comparison.id] = (
                f"the workbook could not be checked: {TABLEAU_ANSWERED} "
                f"{exc.code} {exc.summary}"
            )
            continue
        if comparison.sheet not in tableau.published_sheets(twb):
            skipped[comparison.id] = (
                f"{tableau.NOT_PUBLISHED}; set unpublished: true to compare it anyway"
            )
    return skipped
