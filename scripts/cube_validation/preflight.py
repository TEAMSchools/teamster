"""Read a sheet's workbook XML before proving it, offline.

For each sheet a validation file names, `preflight` lists what the proof will
meet: the shelf fields and the Cube member each maps to, table calculations,
filters (context, code group, relative date, parameter-driven), the parameters
the sheet reads, and whether `sheet_field` is on the sheet. It ends with the
items to settle before `prove`. It reads a local `.twb` and the `members`
cache, and prints no filter or parameter value.
"""

from __future__ import annotations

import re

# trunk-ignore(bandit/B405): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass

from . import discover as finder
from . import tableau
from .builder import Member
from .config import Comparison, ViewConfig

_CLOCK = re.compile(r"\b(?:TODAY|NOW)\s*\(", re.IGNORECASE)
_BRACKETED = re.compile(r"\[([^\[\]]+)\]")
_PARAMETER = re.compile(r"\[Parameters\]\.\[([^\[\]]+)\]")
# What a wide export or a Measure Names value puts before an aggregated
# field's caption: `Avg. Is Mastery Int`, `SUM(Membership)`.
_AGG_PREFIX = re.compile(
    r"^(?:(?:avg|sum|count|countd|min|max|median|attr|agg)\.?(?:\s+of)?\s+)",
    re.IGNORECASE,
)
_AGG_CALL = re.compile(r"^\w+\((.*)\)$")
_ENCODINGS = {"lod": "detail"}
SHOWN_SHARED = 5


@dataclass(frozen=True)
class ShelfField:
    """A field on the rows, the columns or an encoding (`shelf`)."""

    caption: str
    name: str
    shelf: str


@dataclass(frozen=True)
class SheetFilter:
    """One filter. `kinds` holds `context`, `code group`, `relative date` and
    `parameter-driven`, or `regular` alone; `formula` reads a relative date's
    calculation with captions; `source` is a code group's grouped column;
    `columns` the field and every datasource column its calculations read;
    `parameters` the captions of the parameters they read."""

    caption: str
    name: str
    kinds: tuple[str, ...]
    restricting: bool
    formula: str
    group: str
    shared_with: tuple[str, ...]
    source: str
    columns: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ()


@dataclass(frozen=True)
class Parameter:
    """A parameter the sheet reads. Its current value is a member value, so
    preflight never reads it."""

    name: str
    caption: str


@dataclass(frozen=True)
class Sheet:
    """What `preflight` reads from one worksheet."""

    shelf_fields: list[ShelfField]
    table_calcs: list[tableau.TableCalc]
    filters: list[SheetFilter]
    parameters: list[Parameter]
    # Each value field as the sheet shows it, with the names an export gives it.
    values: dict[str, set[str]]


def _plain(text: str) -> str:
    return " ".join(text.split())


def read_sheet(twb_xml: str, sheet: str) -> Sheet:
    """Read one worksheet's fields, table calcs, filters and parameters.

    Raises:
        ValueError: The workbook has no such worksheet.
    """
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    ws = finder.worksheet(root, sheet)
    if ws is None:
        raise ValueError(f"the workbook has no worksheet {sheet!r}")
    caption, personal = finder.sheet_fields(ws)
    for col in root.iter("column"):
        name = finder._bare(col.get("name") or "")
        caption.setdefault(name, col.get("caption") or name)
    formulas = {
        finder._bare(c.name): c.formula for c in finder.calculated_fields(twb_xml)
    }
    groups = finder.group_fields(root)
    calcs = tableau.table_calcs(ws)

    refs: list[tuple[str, str]] = [
        (shelf, el.text or "")
        for shelf, tag in (("rows", "rows"), ("columns", "cols"))
        for el in ws.iter(tag)
    ]
    refs += [
        (_ENCODINGS.get(el.tag, el.tag), el.get("column") or "")
        for enc in ws.iter("encodings")
        for el in enc
    ]
    fields: dict[tuple[str, str], ShelfField] = {}
    values: dict[str, set[str]] = {}
    for shelf, text in refs:
        for m in finder.FIELD_REF.finditer(text):
            if finder.is_value(m):
                shown, names = _value_names(m, caption, calcs)
                values.setdefault(shown, set()).update(names)
            elif m["name"] not in personal:
                fields.setdefault(
                    (m["name"], shelf),
                    ShelfField(caption.get(m["name"], m["name"]), m["name"], shelf),
                )

    def reads(name: str) -> list[str]:
        """`name` and every calculation it reads, through other calculations."""
        seen, todo = [], [name]
        while todo:
            current = todo.pop()
            if current in seen:
                continue
            seen.append(current)
            todo += [
                r
                for r in _BRACKETED.findall(formulas.get(current, ""))
                if r in formulas
            ]
        return seen

    def readable(formula: str) -> str:
        return _plain(_BRACKETED.sub(lambda m: f"[{caption.get(m[1], m[1])}]", formula))

    filter_groups: dict[str, list[str]] = {}
    for other in root.iter("worksheet"):
        for el in other.iter("filter"):
            if el.get("filter-group"):
                filter_groups.setdefault(el.get("filter-group") or "", []).append(
                    other.get("name") or ""
                )

    params = {
        finder._bare(col.get("name") or ""): col
        for ds in root.iter("datasource")
        if ds.get("name") == "Parameters"
        for col in ds.findall("column")
    }

    def param_caption(name: str) -> str:
        return (params[name].get("caption") if name in params else None) or name

    filters = []
    for el in ws.iter("filter"):
        column = el.get("column") or ""
        m = finder.FIELD_REF.search(column)
        name = m["name"] if m else column.rsplit("].[", 1)[-1].strip("[]")
        chain = reads(name)
        kinds = []
        if el.get("context") == "true":
            kinds.append("context")
        if name in groups:
            kinds.append("code group")
        clocked = [n for n in chain if _CLOCK.search(formulas.get(n, ""))]
        if el.get("class") == "relative-date" or clocked:
            kinds.append("relative date")
        if any(_PARAMETER.search(formulas.get(n, "")) for n in chain):
            kinds.append("parameter-driven")
        formula = ""
        if clocked:
            formula = readable(formulas.get(name, ""))
            formula += "".join(
                f"; {caption.get(n, n)} = {readable(formulas[n])}"
                for n in clocked
                if n != name
            )
        group = el.get("filter-group") or ""
        filters.append(
            SheetFilter(
                caption=caption.get(name, name).lstrip(":"),
                name=name,
                kinds=tuple(kinds) or ("regular",),
                # A relative-date filter has no members or range to read; it
                # always narrows the sheet to a window.
                restricting=finder.restricts(el) or el.get("class") == "relative-date",
                formula=formula,
                group=group,
                shared_with=tuple(
                    dict.fromkeys(s for s in filter_groups.get(group, []) if s != sheet)
                ),
                source=_group_source(root, name) if name in groups else "",
                columns=tuple(
                    dict.fromkeys(
                        [name]
                        + [
                            r
                            for n in chain
                            for r in _BRACKETED.findall(formulas.get(n, ""))
                            if r not in formulas and r != "Parameters"
                        ]
                    )
                ),
                parameters=tuple(
                    dict.fromkeys(
                        param_caption(p)
                        for n in chain
                        for p in _PARAMETER.findall(formulas.get(n, ""))
                    )
                ),
            )
        )
    read = [
        finder._bare(col.get("name") or "")
        for deps in ws.iter("datasource-dependencies")
        if deps.get("datasource") == "Parameters"
        for col in deps.findall("column")
    ]
    for name in [f.name for f in filters] + [f.name for f in fields.values()]:
        for n in reads(name):
            read += _PARAMETER.findall(formulas.get(n, ""))
    parameters = [
        Parameter(name, param_caption(name))
        for name in dict.fromkeys(read)
        if name in params
    ]

    return Sheet(list(fields.values()), calcs, filters, parameters, values)


def _value_names(
    m: re.Match, caption: dict[str, str], calcs: list[tableau.TableCalc]
) -> tuple[str, set[str]]:
    """A value field as the sheet shows it, and the bare names it exports as."""
    calc = next((c for c in calcs if c.ref.endswith("." + m[0])), None)
    if calc is not None:
        return calc.caption, {calc.caption.lower()}
    name = m["name"]
    shown = caption.get(name) or name
    agg = finder._AGG_PREFIXES.get(m["deriv"])
    return (f"{agg}({shown})" if agg else shown), {shown.lower()}


def _export_name(field: str) -> str:
    """`Avg. Is Mastery Int` or `AVG(Is Mastery Int)` as `is mastery int`."""
    field = field.strip()
    if call := _AGG_CALL.match(field):
        field = call[1]
    return _AGG_PREFIX.sub("", field).lower()


def _group_source(root: ET.Element, name: str) -> str:
    """The column a code group's codes come from."""
    for col in root.iter("column"):
        calc = col.find("calculation")
        if finder._bare(col.get("name") or "") == name and calc is not None:
            return finder._bare(calc.get("column") or "")
    return ""


@dataclass
class _Checklist:
    lines: list[str]
    before: list[str]

    def add(self, line: str, blocking: str = "") -> None:
        self.lines.append(line)
        if blocking:
            self.before.append(blocking)


def _members_on(view: str, members: list[Member]) -> dict[str, str]:
    """The view's members by short name."""
    return {
        m.name.rsplit(".", 1)[-1]: m.name
        for m in members
        if m.name.startswith(f"{view}.")
    }


def _shelf_lines(
    out: _Checklist,
    view: str,
    comparison: Comparison | None,
    facts: Sheet,
    shaped: Sheet | None,
    members: list[Member],
) -> None:
    on_view = _members_on(view, members)
    known = {m.name for m in members}
    dims = {p.dashboard: p.cube for p in comparison.dims} if comparison else {}
    # A row-level comparison compares at its `rows:` grain, so a shelf field
    # mapped there needs no dim.
    rows = (
        {p.dashboard: p.cube for p in [*comparison.rows.grain, *comparison.rows.values]}
        if comparison and comparison.rows
        else {}
    )
    # Fields the file maps outside `dims` and `rows:`: a filter, by column or
    # caption.
    elsewhere: dict[str, str] = {}
    if comparison:
        for caption, pair in comparison.filters.items():
            elsewhere.setdefault(pair.dashboard, pair.cube)
            elsewhere.setdefault(caption, pair.cube)
    kept = {(f.name, f.shelf) for f in (shaped or facts).shelf_fields}
    original = {(f.name, f.shelf) for f in facts.shelf_fields}
    added = [
        f
        for f in (shaped.shelf_fields if shaped else [])
        if (f.name, f.shelf) not in original
    ]
    if not facts.shelf_fields + added:
        out.add("  Shelf fields: none")
        return
    out.add("  Shelf fields:")
    for f in facts.shelf_fields + added:
        where = f.shelf if f not in added else f"{f.shelf}, added by shelves"
        head = f"    - {f.caption} ({where}): "
        if f.name in dims:
            member = f"{view}.{dims[f.name]}"
        elif f.name in rows:
            member = f"{view}.{rows[f.name]}"
        elif f.name in elsewhere or f.caption in elsewhere:
            member = f"{view}.{elsewhere.get(f.name) or elsewhere[f.caption]}"
        else:
            member = on_view.get(f.name, "")
        if (f.name, f.shelf) not in kept:
            out.add(head + f"{member or 'no Cube member'}; dropped by shelves")
        elif f.name in dims and member not in known:
            out.add(
                head + f"{member}, which members.json does not list",
                f"{f.caption}: dims maps it to {member}, which members.json does "
                "not list; check the name or run `members` again",
            )
        elif f.name in dims:
            out.add(head + member)
        elif f.name in rows:
            out.add(head + f"{member} (rows:)")
        elif member:
            out.add(
                head + f"{member}, not under dims",
                f"{f.caption}: on the {f.shelf}; map it under dims to {member}",
            )
        else:
            out.add(
                head + "no Cube member — reshape with shelves: drop/add, or add a Cube "
                "member",
                f"{f.caption}: no Cube member on the {f.shelf}; reshape with "
                "shelves: drop/add, or add a Cube member",
            )


def _filter_lines(out: _Checklist, comparison: Comparison | None, facts: Sheet) -> None:
    shelves = comparison.shelves if comparison else {}
    cleared = set(shelves.get("clear_filters", []))
    mapped = (
        {p.dashboard for p in comparison.dims}
        | {p.dashboard for p in comparison.filters.values()}
        | set(comparison.filters)
        if comparison
        else set()
    )
    entries = comparison.dashboard_filters if comparison else []
    on_dashboard = {str(e.get("dashboard")) for e in entries}
    # The columns a week-end dashboard filter compares; one handles only a
    # relative-date filter that reads its column.
    week_end = {str(e.get("dashboard")) for e in entries if "days_from_week_end" in e}
    probe_sql = (comparison.probe_sql or "") if comparison else ""
    set_here = set(comparison.parameters) if comparison else set()

    def in_probe(columns: tuple[str, ...]) -> bool:
        # The probe must name the column and a rolling date; a fixed bound on
        # the column is not the sheet's window.
        return "CURRENT_DATE" in probe_sql.upper() and any(
            re.search(rf"\b{re.escape(c)}\b", probe_sql) for c in columns
        )

    # A code group's source column, defaulted through its `filters:` caption.
    defaulted = (
        {
            comparison.filters[d].dashboard
            for d in comparison.defaults
            if d in comparison.filters
        }
        if comparison
        else set()
    )
    lines = []
    for f in facts.filters:
        if not f.restricting:
            continue
        if f.caption in cleared:
            lines.append((f"{f.caption}: cleared by shelves.clear_filters", ""))
        elif f.name in mapped or f.caption in mapped:
            lines.append((f"{f.caption}: mapped", ""))
        elif "relative date" in f.kinds:
            if week_end & set(f.columns):
                lines.append((f"{f.caption}: dashboard_filters days_from_week_end", ""))
            elif in_probe(f.columns):
                lines.append((f"{f.caption}: in probe_sql", ""))
            else:
                need = (
                    f"{f.caption}: relative date; needs dashboard_filters with "
                    "days_from_week_end or a probe filter"
                )
                lines.append((need, need))
        elif "code group" in f.kinds:
            if f.source in defaulted:
                lines.append((f"{f.caption}: defaults narrow {f.source}", ""))
            else:
                need = (
                    f"{f.caption}: code group; clear with shelves.clear_filters, "
                    "or default the comparison to its members"
                )
                lines.append((need, need))
        elif f.name in on_dashboard:
            lines.append((f"{f.caption}: dashboard_filters", ""))
        elif "parameter-driven" in f.kinds and set(f.parameters) <= set_here:
            lines.append((f"{f.caption}: its parameter is set under parameters:", ""))
        elif "parameter-driven" in f.kinds:
            need = (
                f"{f.caption}: driven by a parameter; set it under parameters: or "
                "confirm its current value"
            )
            lines.append((need, need))
        else:
            need = (
                f"{f.caption}: narrows the sheet with no Cube member; map it under "
                "filters:, add dashboard_filters, or clear it"
            )
            lines.append((need, need))
    if not lines:
        out.add("  Restricting filters: none")
        return
    out.add("  Restricting filters:")
    for line, blocking in dict.fromkeys(lines):
        out.add(f"    - {line}", blocking)


def _measure_line(out: _Checklist, comparison: Comparison | None, facts: Sheet) -> None:
    shown = ", ".join(facts.values) or "none"
    wanted = comparison.sheet_field if comparison else None
    if not wanted:
        if len(facts.values) > 1:
            out.add(
                f"  Measure: sheet_field not set; the sheet shows {shown}",
                f"sheet_field: set it; the sheet shows {shown}",
            )
        else:
            out.add(f"  Measure: sheet_field not set; the sheet shows {shown}")
        return
    name = _export_name(wanted)
    found = [s for s, names in facts.values.items() if name in names]
    if found:
        out.add(f"  Measure: sheet_field {wanted!r} is on the sheet ({found[0]})")
    else:
        out.add(
            f"  Measure: sheet_field {wanted!r} is not on the sheet; it shows {shown}",
            f"sheet_field {wanted!r}: not on the sheet; it shows {shown}",
        )


def _sheet_lines(label: str, sheet: str, facts: Sheet) -> list[str]:
    lines = [f"{sheet} ({label})"]
    if facts.table_calcs:
        lines.append("  Table calculations:")
        lines += [f"    - {c.label}" for c in facts.table_calcs]
    else:
        lines.append("  Table calculations: none")
    lines.append("  Filters:")
    for f in facts.filters:
        kinds = ", ".join(f.kinds)
        if f.formula:
            kinds += f" ({f.formula})"
        state = "restricting" if f.restricting else "keeps all"
        line = f"    - {f.caption}: {kinds}; {state}"
        if "relative date" in f.kinds:
            line += (
                "; needs dashboard_filters with days_from_week_end or a probe filter"
            )
        if "code group" in f.kinds:
            line += (
                "; clear with shelves.clear_filters, or default the comparison to "
                "its members"
            )
        if f.shared_with and f.restricting:
            names = ", ".join(f.shared_with[:SHOWN_SHARED])
            more = len(f.shared_with) - SHOWN_SHARED
            names += f" and {more} more" if more > 0 else ""
            line += (
                f"; shared through filter-group {f.group} with {len(f.shared_with)} "
                f"other sheets ({names})"
            )
        lines.append(line)
    if not facts.filters:
        lines[-1] = "  Filters: none"
    if facts.parameters:
        lines.append("  Parameters:")
        lines += [f"    - {p.caption} ({p.name})" for p in facts.parameters]
    else:
        lines.append("  Parameters: none")
    return lines


def check(
    view: str,
    twb_xml: str,
    sheet: str,
    comparison: Comparison | None,
    members: list[Member],
) -> tuple[list[str], list[str]]:
    """One comparison's checklist on its sheet, and its blocking items.

    With no comparison, the sheet's fields are checked against Cube alone.
    """
    facts = read_sheet(twb_xml, sheet)
    out = _Checklist([f"  {comparison.id if comparison else 'No comparison'}:"], [])
    shaped: Sheet | None = None
    reshaped: tableau.Reshaped | None = None
    if comparison and comparison.shelves:
        try:
            reshaped = tableau.set_shelves(twb_xml, sheet, comparison.shelves)
            shaped = read_sheet(reshaped.xml, sheet)
        except ValueError as exc:
            out.before.append(f"shelves: {exc}")

    inner = _Checklist([], out.before)
    _shelf_lines(inner, view, comparison, facts, shaped, members)
    if reshaped is not None and (reshaped.removed or reshaped.recomputed):
        inner.add("  Table calculations:")
        inner.lines += [f"    - removed by shelves.drop: {r}" for r in reshaped.removed]
        inner.lines += [
            f"    - recomputes along the new {shelf}: {', '.join(captions)}"
            for shelf, captions in reshaped.recomputed.items()
        ]
    _filter_lines(inner, comparison, facts)
    set_here = comparison.parameters if comparison else {}
    for p in facts.parameters:
        state = "set under parameters:" if p.caption in set_here else "not set"
        inner.add(f"  Parameter {p.caption}: {state}")
    _measure_line(inner, comparison, shaped or facts)
    wanted = comparison.sheet_field if comparison else None
    for shelf, captions in (reshaped.recomputed if reshaped else {}).items():
        if wanted and _export_name(wanted) in {c.lower() for c in captions}:
            inner.before.append(
                f"sheet_field {wanted!r}: recomputes along the new {shelf} on the "
                "reshaped copy, a number the dashboard never shows"
            )
    out.lines += ["  " + line for line in inner.lines]
    return out.lines, out.before


def report(
    cfg: ViewConfig,
    workbook: Callable[[str | None], tuple[str, str]],
    members: list[Member],
    sheets: list[str] | None = None,
) -> str:
    """The preflight checklist for each sheet the file's comparisons name, or
    for `sheets`.

    `workbook` returns a comparison workbook's label and XML; it is called
    with None for a sheet no comparison names.
    """
    wanted = sheets or list(dict.fromkeys(c.sheet for c in cfg.comparisons if c.sheet))
    blocks = []
    for sheet in wanted:
        comparisons = [c for c in cfg.comparisons if c.sheet == sheet]
        label, xml = workbook(comparisons[0].workbook if comparisons else None)
        try:
            facts = read_sheet(xml, sheet)
        except ValueError:
            blocks.append(f"{sheet}: not in {label}")
            continue
        lines = _sheet_lines(label, sheet, facts)
        for comparison in comparisons or [None]:
            checklist, before = check(cfg.view, xml, sheet, comparison, members)
            lines += checklist
            if before:
                lines.append("    Before prove:")
                lines += [f"      - {b}" for b in dict.fromkeys(before)]
            else:
                lines.append("    Before prove: nothing blocks")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
