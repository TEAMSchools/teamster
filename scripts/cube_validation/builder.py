"""The builder's view of Cube and of a dashboard.

Listing Cube's measures first keeps the builder from adding one Cube already
has, under the same name or another. Inventorying the workbook lists what each
sheet uses, so the missing Cube pieces can be planned.
"""

from __future__ import annotations

# trunk-ignore(bandit/B405): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass

from . import discover as finder
from .cube_client import _FACT, Cube, CubeError, CubeRefusal, bind
from .decisions import sql_fingerprint
from .pipeline import _measure_expression


@dataclass(frozen=True)
class Member:
    """One measure. `sql` is its compiled expression, `fact` the `fct_*` table
    it reads ("" when none)."""

    name: str
    cube: str
    kind: str
    title: str
    description: str
    sql: str
    sql_fingerprint: str
    fact: str


def members(cube: Cube, skipped: list[dict] | None = None) -> list[Member]:
    """Every measure of every cube and view in `/meta`, each compiled alone.

    Compiling asks Cube for SQL and runs nothing in BigQuery. A measure Cube
    cannot compile or bind is left out and, when `skipped` is given, appended
    to it as `{"name", "reason"}`, so one bad measure does not end the listing.
    """
    found = []

    for entry in cube.meta()["cubes"]:
        for measure in entry.get("measures", []):
            name = measure["name"]
            owner, short = name.split(".", 1)

            try:
                compiled = cube.compiled({"measures": [name]})
                sql = _measure_expression(bind(compiled), owner, short)
            except (CubeError, CubeRefusal) as exc:
                if skipped is not None:
                    skipped.append({"name": name, "reason": str(exc)})
                continue

            facts = _FACT.findall(compiled.sql)
            found.append(
                Member(
                    name=name,
                    cube=entry["name"],
                    kind=entry.get("type", "cube"),
                    title=measure.get("title", ""),
                    description=measure.get("description", ""),
                    sql=sql,
                    sql_fingerprint=sql_fingerprint(sql),
                    fact=facts[0] if facts else "",
                )
            )

    return found


def same_sql(found: list[Member]) -> list[list[Member]]:
    """Groups of measures on different cubes with equal SQL over the same fact.

    The expression alone is not enough: `count(distinct t.student_id)` on 2
    facts counts different students. Views are left out: a view member repeats
    its cube's.
    """
    by_sql = defaultdict(list)

    for m in found:
        if m.kind != "view":
            by_sql[(m.fact, m.sql_fingerprint)].append(m)

    return [group for group in by_sql.values() if len({m.cube for m in group}) > 1]


def same_name(found: list[Member], name: str) -> list[Member]:
    """Every member named `name` (the part after the cube) on any cube."""
    return [m for m in found if m.name.split(".", 1)[1] == name]


@dataclass(frozen=True)
class FieldUse:
    """One workbook field and every worksheet that uses it.

    `role` is `measure`, `cut`, `filter` or `parameter`. `formula` has code
    groups expanded. `presentation` marks what Cube should not model: a
    parameter, a URL, or a field built on the viewer's identity.
    """

    caption: str
    name: str
    role: str
    formula: str
    sheets: tuple[str, ...]
    presentation: bool


_ROLE_ORDER = ("parameter", "measure", "cut", "filter")


def _sheet_uses(ws: ET.Element) -> dict[tuple[str, str], str]:
    """A worksheet's fields as `(aggregation, bare name)`, each with the role the
    sheet gives it. The aggregation is `""` unless a raw field is aggregated.

    A cut wins over a filter on the same field, and a measure over both.
    """
    uses: dict[tuple[str, str], str] = {}

    def add(key: tuple[str, str], role: str) -> None:
        if key not in uses or _ROLE_ORDER.index(role) < _ROLE_ORDER.index(uses[key]):
            uses[key] = role

    roles = {
        finder._bare(col.get("name") or ""): col.get("role")
        for col in ws.iter("column")
    }
    for col in ws.iter("column"):
        if col.get("param-domain-type"):
            add(("", finder._bare(col.get("name") or "")), "parameter")

    def field_of(ref: str) -> tuple[tuple[str, str], str] | None:
        m = finder.FIELD_REF.search(ref)
        if m is None:
            return None
        if m["deriv"] in finder._AGG_PREFIXES:
            return (finder._AGG_PREFIXES[m["deriv"]], m["name"]), "measure"
        if m["deriv"] == "usr":
            # `usr` is also in AGGREGATES: it marks a calculation, whose role
            # says whether it aggregates.
            role = "measure" if roles.get(m["name"]) == "measure" else "cut"
            return ("", m["name"]), role
        if finder.is_value(m):
            return None
        return ("", m["name"]), "cut"

    shelves = " ".join(
        [el.text or "" for el in ws.iter() if el.tag in ("rows", "cols")]
        + [el.get("column") or "" for enc in ws.iter("encodings") for el in enc]
    )
    for ref in finder.FIELD_REF.finditer(shelves):
        if found := field_of(ref[0]):
            add(*found)

    shelf_fields = set(uses)
    for filter_el in ws.iter("filter"):
        found = field_of(filter_el.get("column") or "")
        if found and found[0] not in shelf_fields:
            add(found[0], "filter")

    return uses


def workbook_inventory(twb_xml: str) -> list[FieldUse]:
    """Every field each worksheet uses, one entry per field, sheets merged.

    Fields are read the way `sheet_gaps` reads a sheet: shelves and encodings
    for measures and cuts, `filter` elements for filters, and a datasource
    column with `param-domain-type` for a parameter. A field used in more than
    one role takes the first of parameter, measure, cut, filter. A worksheet
    without a name is read as `""`.

    Raises:
        xml.etree.ElementTree.ParseError: `twb_xml` is not XML.
    """
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    calcs = {finder._bare(c.name): c.formula for c in finder.calculated_fields(twb_xml)}
    raw = {
        (c.formula.split("(", 1)[0], finder._bare(c.name)): c.formula
        for c in finder.aggregated_fields(twb_xml)
    }
    found_bins = finder.bins(twb_xml)

    def formula_of(agg: str, bare: str) -> str:
        if agg and bare in calcs:
            return f"{agg}({calcs[bare]})"
        if agg:
            return raw.get((agg, bare), "")
        return calcs.get(bare) or found_bins.get(bare, "")

    merged: dict[tuple[str, str], dict] = {}
    for ws in root.iter("worksheet"):
        sheet = ws.get("name") or ""
        caption, personal = finder.sheet_fields(ws)
        for (agg, bare), role in _sheet_uses(ws).items():
            shown = caption.get(bare, bare)
            entry = merged.setdefault(
                (agg, bare),
                {
                    "caption": f"{agg}({shown})" if agg else shown,
                    "role": role,
                    "sheets": set(),
                    "personal": False,
                },
            )
            if _ROLE_ORDER.index(role) < _ROLE_ORDER.index(entry["role"]):
                entry["role"] = role
            entry["sheets"].add(sheet)
            entry["personal"] |= bare in personal

    uses = []
    for (agg, bare), entry in merged.items():
        formula = finder.explain_bins(formula_of(agg, bare), found_bins)
        presentation = (
            entry["role"] == "parameter"
            or entry["personal"]
            or "http" in formula.lower()
            or bool(finder.USER_FUNCTION.search(formula))
        )
        uses.append(
            FieldUse(
                caption=entry["caption"],
                name=f"{agg}({bare})" if agg else bare,
                role=entry["role"],
                formula=formula,
                sheets=tuple(sorted(entry["sheets"])),
                presentation=presentation,
            )
        )
    return sorted(uses, key=lambda u: (u.caption.lower(), u.name))
