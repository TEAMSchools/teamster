"""The builder's view of Cube and of a dashboard.

Listing Cube's measures and dimensions first keeps the builder from adding one Cube already
has, under the same name or another. Inventorying the workbook lists what each
sheet uses, so the missing Cube pieces can be planned. Joining that list with
the gap catalog and the dashboard's Asana task gives one row per field.
"""

from __future__ import annotations

import re

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
    """One measure or dimension. For a measure, `kind` is its cube's type; for a
    dimension it is `dimension`. `sql` is a measure's compiled expression, `fact`
    the `fct_*` table it reads ("" when none; both "" for a dimension)."""

    name: str
    cube: str
    kind: str
    title: str
    description: str
    sql: str
    sql_fingerprint: str
    fact: str


def members(cube: Cube, skipped: list[dict] | None = None) -> list[Member]:
    """Every measure and dimension of every cube and view in `/meta`.

    Each measure is compiled alone; a dimension is listed as `/meta` gives it,
    with no SQL. Compiling asks Cube for SQL and runs nothing in BigQuery. A measure Cube
    cannot compile or bind is left out and, when `skipped` is given, appended
    to it as `{"name", "reason"}`, so one bad measure does not end the listing.
    """
    found = []

    for entry in cube.meta()["cubes"]:
        for dim in entry.get("dimensions", []):
            found.append(
                Member(
                    name=dim["name"],
                    cube=entry["name"],
                    kind="dimension",
                    title=dim.get("title", ""),
                    description=dim.get("description", ""),
                    sql="",
                    sql_fingerprint="",
                    fact="",
                )
            )

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
    its cube's, and a dimension has no SQL to compare.
    """
    by_sql = defaultdict(list)

    for m in found:
        if m.kind != "view" and m.sql_fingerprint:
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


def catalog_rows(markdown: str, slug: str) -> list[dict]:
    """The `### Measures` and `### Dimensions` rows of one dashboard's section
    of the gap catalog, as `{"field", "kind", "status", "where"}`.

    The section is the one headed `## <Dashboard> (`<slug>`)`. `field` is the
    first column and the cells are kept as written; `status` and `where` are
    the columns with those headers, `""` when a table has none.
    """
    heading = re.compile(rf"^## .*\(`{re.escape(slug)}`\)\s*$")
    rows: list[dict] = []
    in_section = False
    kind = ""
    columns: dict[str, int] | None = None

    for line in markdown.splitlines():
        if line.startswith("## "):
            in_section = bool(heading.match(line))
            kind, columns = "", None
        elif not in_section:
            continue
        elif line.startswith("#"):
            title = line.lstrip("#").strip().lower()
            kind = {"measures": "measure", "dimensions": "dimension"}.get(title, "")
            columns = None
        elif kind and line.startswith("|"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if columns is None:
                columns = {c.lower(): i for i, c in enumerate(cells)}
            elif not all(set(c) <= set("-: ") for c in cells):
                cells += [""] * (len(columns) - len(cells))
                rows.append(
                    {
                        "field": cells[0],
                        "kind": kind,
                        "status": cells[columns["status"]]
                        if "status" in columns
                        else "",
                        "where": cells[columns["where"]] if "where" in columns else "",
                    }
                )

    return rows


@dataclass(frozen=True)
class InventoryRow:
    """One field of a dashboard across the catalog, the workbook review and
    Asana. `member` is the Cube member it maps to ("" when none).
    `disagreement` says in plain words where the sources differ ("" when they
    agree)."""

    field: str
    kind: str
    member: str
    sources: tuple[str, ...]
    disagreement: str


_AGG_CAPTION = re.compile(
    "(?:" + "|".join(finder._AGG_PREFIXES.values()) + r")\((.*)\)", re.IGNORECASE
)
_CATALOG_STATUSES = ("cube-covered", "mart-ready", "mart-missing", "workbook-only")
_MEMBER_REF = re.compile(r"`(\w+\.\w+)`")


def _plain(text: str) -> str:
    """`text` without backticks, bold marks or parentheticals, trimmed."""
    text = text.replace("`", "").replace("**", "")
    while (stripped := re.sub(r"\([^()]*\)", "", text)) != text:
        text = stripped
    return " ".join(text.split())


def _catalog_names(field: str) -> list[str]:
    """The names a catalog first cell lists: split on commas and slashes after
    the parentheticals are stripped, so `Tier (A/B), Is Low` is 2 names."""
    return [n for part in re.split(r"[,/]", _plain(field)) if (n := part.strip())]


def _cell_matches(field: str, name: str) -> bool:
    """Whether a catalog first cell names `name`.

    The whole cell and its first comma fragment match by containment. Later
    fragments (after a comma or slash) match only an equal name, so a note such
    as `overall/standard toggle` does not pull in every field containing
    `overall`.
    """
    whole = _plain(field)
    first = whole.split(",", 1)[0].strip()
    return (
        _same_field(whole, name)
        or _same_field(first, name)
        or any(n.lower() == name.lower() for n in _catalog_names(field))
    )


def _caption_name(caption: str) -> str:
    """A review caption to match on; `SUM(x)` matches as `x`, not as `SUM`."""
    if m := _AGG_CAPTION.fullmatch(caption.strip()):
        return _plain(m[1])
    return _plain(caption)


def _same_field(a: str, b: str) -> bool:
    """Whether either text contains the other, ignoring case, on word
    boundaries."""
    a, b = a.lower(), b.lower()

    def inside(needle: str, hay: str) -> bool:
        return bool(re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay))

    return bool(a and b) and (inside(a, b) or inside(b, a))


def _statuses(texts: list[str]) -> set[str]:
    lowered = " ".join(texts).lower()
    return {s for s in _CATALOG_STATUSES if s in lowered}


def _find_member(
    found: list[Member], wheres: list[str], bare: str, caption: str, kind: str
) -> tuple[str, bool]:
    """The member for a field and whether several matched by name or title.

    A backticked member in a catalog `where` cell wins, then a member whose
    short name is `bare`, then one titled `caption`. Name and title matches
    are limited to the field's `kind` when it has one. A view repeats its
    cube's measures, so views are used only when no cube matches.
    """
    by_name = {m.name: m for m in found}
    for where in wheres:
        for ref in _MEMBER_REF.findall(where):
            if ref in by_name:
                return ref, False

    def pick(hits: list[Member]) -> tuple[str, bool] | None:
        hits = [m for m in hits if m.kind != "view"] or hits
        if not hits:
            return None
        return (hits[0].name, False) if len(hits) == 1 else ("", True)

    if kind:
        found = [m for m in found if (m.kind == "dimension") == (kind == "dimension")]
    by_short = [m for m in found if m.name.split(".", 1)[1] == bare]
    by_title = [m for m in found if m.title.lower() == caption.lower() != ""]
    return pick(by_short) or pick(by_title) or ("", False)


def inventory(
    catalog: list[dict],
    review: list[FieldUse],
    asana: list[dict],
    found: list[Member],
) -> list[InventoryRow]:
    """One row per field across the catalog, the workbook review and Asana.

    The review list is the backbone: a catalog or Asana row joins a review
    field when either name contains the other (see `_cell_matches` for how a
    catalog first cell is read). Rows that match no review field,
    and Asana rows matching no catalog row either, become rows of their own.
    A field the review marks as presentation is left out, with whatever
    catalog or Asana rows name it. A catalog row that joins more than one review
    field is noted on each. Deferred Asana items are listed and marked, not
    dropped.
    """
    joined = {id(r): False for r in catalog}
    fields_of = {id(r): 0 for r in catalog}
    groups = []  # (review field | None, catalog rows, asana rows)

    for use in review:
        name = _caption_name(use.caption)
        rows = [r for r in catalog if _cell_matches(r["field"], name)]
        for r in rows:
            joined[id(r)] = True
            if not use.presentation:
                fields_of[id(r)] += 1
        groups.append([use, rows, []])

    for r in catalog:
        if not joined[id(r)]:
            groups.append([None, [r], []])

    for item in asana:
        name = _plain(item["field"])
        hits = [
            g
            for g in groups
            if g[0] is not None and _same_field(_caption_name(g[0].caption), name)
        ] or [
            g
            for g in groups
            if g[0] is None and g[1] and _cell_matches(g[1][0]["field"], name)
        ]
        if hits:
            for g in hits:
                g[2].append(item)
        else:
            groups.append([None, [], [item]])

    rows_out = []
    for use, cat_rows, asana_rows in groups:
        if use is not None and use.presentation:
            continue

        if use is not None:
            field = use.caption
            kind = "measure" if use.role == "measure" else "dimension"
            bare = _AGG_CAPTION.fullmatch(use.name.strip())
            bare = bare[1] if bare else use.name
            caption = _caption_name(use.caption)
        elif cat_rows:
            field = _plain(cat_rows[0]["field"]) or cat_rows[0]["field"]
            kind = cat_rows[0]["kind"]
            bare = ""
            caption = field
        else:
            field = asana_rows[0]["field"]
            kind = ""
            bare = ""
            caption = _plain(field)

        sources = tuple(
            label
            for label, present in (
                ("catalog", bool(cat_rows)),
                ("review", use is not None),
                ("asana", bool(asana_rows)),
            )
            if present
        )

        member, several = "", False
        if kind or not cat_rows:
            member, several = _find_member(
                found, [r["where"] for r in cat_rows], bare, caption, kind
            )

        notes = []
        if len(sources) == 1 and sources[0] != "review":
            notes.append(f"only in {sources[0]}")
        elif use is not None and not cat_rows:
            notes.append("not in catalog")

        statuses = _statuses([r["status"] for r in cat_rows])
        if several:
            notes.append(f"members named {bare or caption} on several cubes")
        elif statuses:
            if not member and "cube-covered" in statuses:
                notes.append("catalog says cube-covered, no member found")
            elif member and "cube-covered" not in statuses:
                first = next(s for s in _CATALOG_STATUSES if s in statuses)
                notes.append(f"catalog says {first}, member found")

        if any(fields_of[id(r)] > 1 for r in cat_rows):
            notes.append("catalog row matches several fields")

        if any(a.get("status") == "deferred" for a in asana_rows):
            notes.append("deferred in asana")

        rows_out.append(InventoryRow(field, kind, member, sources, "; ".join(notes)))

    return rows_out
