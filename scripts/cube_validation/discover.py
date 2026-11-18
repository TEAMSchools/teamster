"""Find candidate Tableau comparisons for a Cube measure.

Reads the dbt Tableau exposures and each workbook's calculated fields and
aggregated raw fields, then ranks them by how many name tokens they share with
the measure and its SQL. It also reads a sheet's shape: shelves, export form,
filters and displayed decimals. Nothing is written: `discover` prints the
candidates and the analyst confirms each one.
"""

from __future__ import annotations

import re

# trunk-ignore(bandit/B405): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .tableau import displayed_decimals

TOP_N = 5
MIN_TOKEN_LENGTH = 3
SQL_KEYWORDS = frozenset(
    {
        "select",
        "from",
        "where",
        "case",
        "when",
        "then",
        "else",
        "end",
        "sum",
        "avg",
        "count",
        "and",
        "or",
        "not",
        "null",
        "is",
        "as",
        "distinct",
        "nullif",
        "cast",
    }
)
_REF = re.compile(r"""ref\(\s*["']([^"']+)["']\s*\)""")

# A shelf or filter field: `[derivation:name:type]`, with an optional `:N`.
# Measure Names, user filters and action filters have no derivation, so they
# never match.
FIELD_REF = re.compile(r"\[(?P<deriv>[a-z]*):(?P<name>[^\]]+?):[a-z]+(?::\d+)?\]")
# Derivations that aggregate a field; such a field is a value, not a cut.
AGGREGATES = {
    "sum", "avg", "cnt", "ctd", "cntd", "min", "max", "attr", "med", "usr",
    "std", "stp", "var", "vrp", "pcto", "pctd", "kurt", "skew", "collect",
}  # fmt: skip
# A field built on the viewer's identity is a permission, not a cut.
USER_FUNCTION = re.compile(
    r"\b(USERNAME|FULLNAME|USERDOMAIN|ISMEMBEROF|ISUSERNAME|ISFULLNAME|"
    r"USERATTRIBUTE|USERATTRIBUTEINCLUDES)\s*\(",
    re.IGNORECASE,
)
# Aggregations as a column-instance names them, and as its ref abbreviates them.
_AGG_NAMES = {
    "Sum": "SUM", "Avg": "AVG", "Count": "COUNT", "CountD": "COUNTD",
    "Min": "MIN", "Max": "MAX", "Median": "MEDIAN",
}  # fmt: skip
_AGG_PREFIXES = {
    "sum": "SUM", "avg": "AVG", "cnt": "COUNT", "ctd": "COUNTD",
    "min": "MIN", "max": "MAX", "med": "MEDIAN",
}  # fmt: skip
# Filter fields whose chosen values `discover` prints. Any other field's values
# stay hidden: they can name a person, and a printed value gets copied.
SHOWN_FILTER_FIELDS = frozenset(
    {
        "academic_year",
        "region",
        "enroll_status",
        "grade_level",
        "school_level",
        "school_abbreviation",
        "term",
    }
)


@dataclass(frozen=True)
class Exposure:
    name: str
    label: str
    luid: str
    models: list[str]


class ExposureList(list[Exposure]):
    """Parsed exposures; `skipped` names entries without a luid or models."""

    def __init__(self) -> None:
        super().__init__()
        self.skipped: list[str] = []


@dataclass(frozen=True)
class Calc:
    caption: str
    formula: str
    worksheets: list[str]
    name: str = ""


@dataclass(frozen=True)
class Candidate:
    workbook_luid: str
    workbook_label: str
    worksheets: list[str]
    caption: str
    formula: str
    score: float


def tableau_exposures(path: Path) -> ExposureList:
    """Read the workbook luid and models of each Tableau exposure.

    The luid sits at `config.meta.dagster.asset.metadata.id`. An exposure
    missing the luid or `depends_on` is left out and named in `skipped`.

    Args:
        path: The exposures YAML file.

    Returns:
        The usable exposures, in file order.
    """
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = ExposureList()
    for entry in doc.get("exposures") or []:
        name = str(entry.get("name", ""))
        luid = _dig(entry, "config", "meta", "dagster", "asset", "metadata", "id")
        models = [
            m.group(1)
            for dep in entry.get("depends_on") or []
            if (m := _REF.search(str(dep)))
        ]
        if not luid or not models:
            out.skipped.append(name)
            continue
        out.append(Exposure(name, str(entry.get("label", name)), str(luid), models))
    return out


def _dig(node: object, *keys: str) -> object:
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def calculated_fields(twb_xml: str) -> list[Calc]:
    """List a workbook's calculated fields and the worksheets that use them.

    A calculated field is a `<column>` holding a `<calculation>` under a
    `<datasource>`. A worksheet uses it when its `<datasource-dependencies>`
    lists the column or an instance of it. XML escapes in formulas are decoded
    by the parser.

    Args:
        twb_xml: The text of a `.twb` file.

    Returns:
        One `Calc` per distinct calculated field, ordered by caption.
    """
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)

    used_by: dict[str, set[str]] = {}
    for sheet in root.iter("worksheet"):
        sheet_name = sheet.get("name") or ""
        for deps in sheet.iter("datasource-dependencies"):
            for el in deps:
                ref = (
                    el.get("column") if el.tag == "column-instance" else el.get("name")
                )
                if ref:
                    used_by.setdefault(ref, set()).add(sheet_name)

    found: dict[str, Calc] = {}
    for datasource in root.iter("datasource"):
        for column in datasource.findall("column"):
            calc = column.find("calculation")
            name = column.get("name") or ""
            formula = calc.get("formula") if calc is not None else None
            if not formula or name in found:
                continue
            caption = column.get("caption") or name.strip("[]")
            found[name] = Calc(caption, formula, sorted(used_by.get(name, set())), name)
    return sorted(found.values(), key=lambda c: c.caption)


def _bare(name: str) -> str:
    return name[1:-1] if name.startswith("[") and name.endswith("]") else name


def _unquote(text: str | None) -> str:
    text = text or ""
    return text[1:-1] if len(text) > 1 and text[0] == text[-1] == '"' else text


def bins(twb_xml: str) -> dict[str, str]:
    """Map each categorical bin (a code group) to its groups and codes.

    Returns:
        Bin name (as formulas name it) to text such as `Tardy = T, ET; Absent = A`.
    """
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    out: dict[str, str] = {}
    for column in root.iter("column"):
        calc = column.find("calculation")
        if calc is None or calc.get("class") != "categorical-bin":
            continue
        groups = [
            f"{_unquote(b.get('value'))} = "
            + ", ".join(_unquote(v.text) for v in b.findall("value"))
            for b in calc.findall("bin")
        ]
        out.setdefault(_bare(column.get("name") or ""), "; ".join(groups))
    return out


def explain_bins(formula: str, found: dict[str, str]) -> str:
    """Append the codes of each bin a formula uses, so its groups read plainly."""
    used = [name for name in found if f"[{name}]" in formula]
    if not used:
        return formula
    return formula + "  " + " ".join(f"[{name}: {found[name]}]" for name in used)


def aggregated_fields(twb_xml: str) -> list[Calc]:
    """List raw fields a sheet aggregates directly, such as `SUM(Membership)`.

    These are column-instances, not calculated fields, so `calculated_fields`
    misses them.
    """
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    captions: dict[str, str] = {}
    calculated: set[str] = set()
    for column in root.iter("column"):
        name = column.get("name") or ""
        if column.get("caption"):
            captions.setdefault(name, column.get("caption") or "")
        if column.find("calculation") is not None:
            calculated.add(name)
    found: dict[tuple[str, str], set[str]] = {}
    for sheet in root.iter("worksheet"):
        for inst in sheet.iter("column-instance"):
            agg = _AGG_NAMES.get(inst.get("derivation") or "")
            column = inst.get("column") or ""
            if agg and column not in calculated:
                found.setdefault((agg, column), set()).add(sheet.get("name") or "")
    return sorted(
        (
            Calc(
                f"{agg}({captions.get(column, _bare(column))})",
                f"{agg}({column})",
                sorted(sheets),
                column,
            )
            for (agg, column), sheets in found.items()
        ),
        key=lambda c: c.caption,
    )


def is_value(m: re.Match) -> bool:
    """True for a ref to a value, not a cut: an aggregate, or a table
    calculation over one (`[cum:ctd:student_number:qk]` nests a derivation).
    """
    return m["deriv"] in AGGREGATES or ":" in m["name"]


# Calculation classes of a group (`categorical-bin`) or bin field. A filter
# names one bare (`[ds].[Discipline]`), with no derivation prefix.
GROUP_CLASSES = frozenset({"categorical-bin", "bin"})


def group_fields(ws: ET.Element) -> set[str]:
    """Bare names of the sheet's group and bin fields."""
    return {
        _bare(col.get("name") or "")
        for col in ws.iter("column")
        if (calc := col.find("calculation")) is not None
        and calc.get("class") in GROUP_CLASSES
    }


def filter_field(column: str, groups: set[str]) -> str | None:
    """The bare field a filter's column names, or None for a value or a ref
    with no derivation prefix that names no group field.
    """
    m = FIELD_REF.search(column)
    if m is not None:
        return None if is_value(m) else m["name"]
    name = column.rsplit("].[", 1)[-1].rstrip("]") if "].[" in column else ""
    return name if name in groups else None


def restricts(filter_el: ET.Element) -> bool:
    """True when a filter is set to chosen values or a range, not All."""
    if filter_el.get("class") == "quantitative":
        return any(c.tag in ("min", "max") for c in filter_el)
    top = filter_el.find("groupfilter")
    if top is None:
        return False
    # `level-members` is every member of the level, whatever `ui-enumeration`
    # the filter card shows.
    return top.get("function") != "level-members"


@dataclass(frozen=True)
class SheetShape:
    rows: list[str]
    cols: list[str]
    long_export: bool
    filters: list[str] = field(default_factory=list)
    decimals: dict[str, int] = field(default_factory=dict)


def worksheet(root: ET.Element, sheet: str) -> ET.Element | None:
    return next((w for w in root.iter("worksheet") if w.get("name") == sheet), None)


def sheet_fields(ws: ET.Element) -> tuple[dict[str, str], set[str]]:
    """A worksheet's field captions by bare name, and its identity-based fields."""
    caption: dict[str, str] = {}
    personal: set[str] = set()
    for col in ws.iter("column"):
        name = _bare(col.get("name") or "")
        caption.setdefault(name, col.get("caption") or name)
        calc = col.find("calculation")
        if calc is not None and USER_FUNCTION.search(calc.get("formula") or ""):
            personal.add(name)
    return caption, personal


def _ref_caption(m: re.Match, caption: dict[str, str]) -> str | None:
    """A shelf or format ref as the sheet shows it: `SUM(Membership)`, `# Tardy`."""
    name = caption.get(m["name"], m["name"])
    if m["deriv"] in ("usr", "none", ""):
        return name
    agg = _AGG_PREFIXES.get(m["deriv"])
    return f"{agg}({name})" if agg else None


def sheet_shape(twb_xml: str, sheet: str) -> SheetShape:
    """Read a sheet's shelves, export form, filters and displayed decimals.

    A filter set to chosen values shows them only for a field in
    `SHOWN_FILTER_FIELDS`; any other field's values stay hidden. Permission
    fields and filters on aggregated values are left out.

    Raises:
        ValueError: The workbook has no such worksheet.
    """
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    ws = worksheet(root, sheet)
    if ws is None:
        raise ValueError(f"the workbook has no worksheet {sheet!r}")
    caption, personal = sheet_fields(ws)
    groups = group_fields(ws)

    def shelf(tag: str) -> list[str]:
        text = " ".join(el.text or "" for el in ws.iter(tag))
        out = []
        for m in FIELD_REF.finditer(text):
            if not is_value(m):
                name = caption.get(m["name"], m["name"])
                if name not in out:
                    out.append(name)
        return out

    shelves = " ".join(el.text or "" for el in ws.iter() if el.tag in ("rows", "cols"))

    decimals: dict[str, int] = {}
    for fmt in ws.iter("format"):
        if fmt.get("attr") != "text-format":
            continue
        m = FIELD_REF.search(fmt.get("field") or "")
        shown = _ref_caption(m, caption) if m else None
        # An empty format sets no displayed decimals.
        if shown and fmt.get("value"):
            decimals.setdefault(shown, displayed_decimals(fmt.get("value") or ""))

    filters = []
    for filter_el in ws.iter("filter"):
        field_name = filter_field(filter_el.get("column") or "", groups)
        if field_name is None or field_name in personal:
            continue
        name = caption.get(field_name, field_name)
        if not restricts(filter_el):
            filters.append(f"{name}: All")
        elif filter_el.get("class") == "quantitative":
            filters.append(f"{name}: a range (narrows the sheet)")
        elif field_name in SHOWN_FILTER_FIELDS:
            top = filter_el.find("groupfilter")
            members = ", ".join(
                _unquote(g.get("member")) for g in filter_el.iter("groupfilter")
                if g.get("member") is not None
            )  # fmt: skip
            if top is not None and top.get("function") == "except":
                members = f"all except {members}"
            filters.append(f"{name}: {members} (narrows the sheet)")
        else:
            filters.append(
                f"{name}: chosen values hidden (narrows the sheet); "
                "decide whether the probe needs it"
            )

    return SheetShape(
        rows=shelf("rows"),
        cols=shelf("cols"),
        long_export="[:Measure Names]" in shelves,
        # A date can carry 2 filters (a part and a range) that read the same.
        filters=list(dict.fromkeys(filters)),
        decimals=decimals,
    )


def _tokens(text: str) -> set[str]:
    parts = re.split(r"[^A-Za-z0-9]+", text.lower())
    return {p for p in parts if len(p) >= MIN_TOKEN_LENGTH and p not in SQL_KEYWORDS}


def rank(
    measure: str,
    member_sql: str,
    calcs: list[Calc],
    workbook_luid: str = "",
    workbook_label: str = "",
    *,
    caption: str | None = None,
    limit: int | None = TOP_N,
) -> list[Candidate]:
    """Rank one workbook's fields against a measure.

    The score is the shared tokens over the union of the measure's and the SQL's
    tokens (0 to 1). A token found in the formula counts the same as one in
    the caption. A field whose caption contains `caption` (the name the
    dashboard shows) gains 1, so it ranks first even with no shared token.

    Args:
        measure: The Cube measure name.
        member_sql: The SQL expression behind the measure.
        calcs: The workbook's calculated fields.
        workbook_luid: Carried onto each candidate.
        workbook_label: Carried onto each candidate.
        caption: The dashboard's name for the measure, matched without case.
        limit: How many to return; None returns every candidate.

    Returns:
        Up to `limit` candidates with a score above 0, best first, ties by
        caption.
    """
    wanted = _tokens(measure) | _tokens(member_sql)
    if not wanted and not caption:
        return []
    scored = []
    for calc in calcs:
        shared = wanted & (_tokens(calc.caption) | _tokens(calc.formula))
        boost = 1.0 if caption and caption.lower() in calc.caption.lower() else 0.0
        if shared or boost:
            scored.append(
                Candidate(
                    workbook_luid,
                    workbook_label,
                    calc.worksheets,
                    calc.caption,
                    calc.formula,
                    boost + (len(shared) / len(wanted) if wanted else 0.0),
                )
            )
    scored.sort(key=lambda c: (-c.score, c.caption))
    return scored if limit is None else scored[:limit]
