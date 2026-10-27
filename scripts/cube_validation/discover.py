"""Find candidate Tableau comparisons for a Cube measure.

Reads the dbt Tableau exposures and each workbook's calculated fields, then
ranks the fields by how many name tokens they share with the measure and its
SQL. Nothing is written: `discover` prints the candidates and the analyst
confirms each one.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import yaml

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
            found[name] = Calc(caption, formula, sorted(used_by.get(name, set())))
    return sorted(found.values(), key=lambda c: c.caption)


def _tokens(text: str) -> set[str]:
    parts = re.split(r"[^A-Za-z0-9]+", text.lower())
    return {p for p in parts if len(p) >= MIN_TOKEN_LENGTH and p not in SQL_KEYWORDS}


def rank(
    measure: str,
    member_sql: str,
    calcs: list[Calc],
    workbook_luid: str = "",
    workbook_label: str = "",
) -> list[Candidate]:
    """Rank one workbook's calculated fields against a measure.

    The score is the shared tokens over the union of the measure's and the SQL's
    tokens (0 to 1). A token found in the formula counts the same as one in
    the caption.

    Args:
        measure: The Cube measure name.
        member_sql: The SQL expression behind the measure.
        calcs: The workbook's calculated fields.
        workbook_luid: Carried onto each candidate.
        workbook_label: Carried onto each candidate.

    Returns:
        Up to five candidates with a score above 0, best first, ties by caption.
    """
    wanted = _tokens(measure) | _tokens(member_sql)
    if not wanted:
        return []
    scored = []
    for calc in calcs:
        shared = wanted & (_tokens(calc.caption) | _tokens(calc.formula))
        if shared:
            scored.append(
                Candidate(
                    workbook_luid,
                    workbook_label,
                    calc.worksheets,
                    calc.caption,
                    calc.formula,
                    len(shared) / len(wanted),
                )
            )
    scored.sort(key=lambda c: (-c.score, c.caption))
    return scored[:TOP_N]
