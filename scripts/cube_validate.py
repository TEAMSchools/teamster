"""Compare Cube with what a Tableau dashboard shows, at every grain its sheets use.

    uv run scripts/cube_validate.py grains <workbook.twb> --dashboard "<name>" [...] [--measure "<caption>"]
    uv run scripts/cube_validate.py run <checks.yml> [--rows <gid,...>] [--scope-only]

`grains` reads a downloaded .twb and proposes the grains for one measure's check entry.
`run` needs CUBE_API_SECRET, which only the pytest secrets fixture provides, so it runs
inside a throwaway tests/test_zz_*.py. Runbook: .claude/skills/cube-dashboard/SKILL.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import defusedxml.ElementTree as SafeET

if TYPE_CHECKING:
    # trunk-ignore(bandit/B405): type-only import; parsing goes through defusedxml
    import xml.etree.ElementTree as ET

# [federated.<datasource>].[<derivation>:<field>:<type>], or [federated.<ds>].[<named filter>]
_TOKEN = re.compile(r"\[(federated\.[^\]]+)\]\.\[([^\]]+)\]")
_INSTANCE = re.compile(r"^([a-z]+):(.+):([a-z]+)$")
_DATE_PARTS = {
    "yr": "year",
    "tyr": "year",
    "qr": "quarter",
    "tqr": "quarter",
    "mn": "month",
    "tmn": "month",
    "wk": "week",
    "twk": "week",
    "dy": "day",
    "tdy": "day",
}
_MEASURE_DERIVATIONS = {"sum", "avg", "cnt", "ctd", "min", "max", "med", "usr", "agg"}


@dataclass
class Sheet:
    name: str
    dashboards: list[str]
    datasource: str = ""
    measures: dict[str, str] = field(default_factory=dict)  # caption -> formula
    shelf_dims: list[str] = field(default_factory=list)
    filter_dims: list[str] = field(default_factory=list)
    other_filters: list[str] = field(default_factory=list)


def _attr(e: ET.Element, key: str) -> str:
    return e.get(key) or ""


def _columns(root: ET.Element) -> dict[tuple[str, str], tuple[str, str]]:
    """(datasource name, '[field]') -> (caption, formula)."""
    out = {}
    for ds in root.findall("datasources/datasource"):
        for col in ds.findall("column"):
            calc = col.find("calculation")
            out[(_attr(ds, "name"), _attr(col, "name"))] = (
                _attr(col, "caption") or _attr(col, "name").strip("[]"),
                _attr(calc, "formula") if calc is not None else "",
            )
    return out


def _classify(ds: str, inner: str, columns) -> tuple[str, str, str]:
    """Return (kind, label, formula); kind is 'dim', 'measure' or 'other'."""
    m = _INSTANCE.match(inner)
    if not m:
        return "other", inner, ""
    deriv, fld, _ = m.groups()
    caption, formula = columns.get((ds, f"[{fld}]"), (fld, ""))
    if deriv == "none":
        return "dim", caption, formula
    if deriv in _DATE_PARTS:
        return "dim", f"{caption}@{_DATE_PARTS[deriv]}", formula
    if deriv in _MEASURE_DERIVATIONS:
        return "measure", caption, formula
    return "other", caption, formula


def parse_twb(path: str | Path, dashboards: list[str]) -> list[Sheet]:
    """Every worksheet placed on one of `dashboards`, with its shelves and filters."""
    root = SafeET.parse(path).getroot()  # defusedxml: no entity expansion
    if root is None:
        raise ValueError(f"{path}: empty workbook")
    columns = _columns(root)
    ds_caption = {
        _attr(d, "name"): _attr(d, "caption") or _attr(d, "name")
        for d in root.findall("datasources/datasource")
    }
    placed: dict[str, list[str]] = {}
    for d in root.findall("dashboards/dashboard"):
        if _attr(d, "name") in dashboards:
            for z in d.iter("zone"):
                on = placed.setdefault(_attr(z, "name"), []) if z.get("name") else None
                if on is not None and _attr(d, "name") not in on:
                    on.append(_attr(d, "name"))
    sheets = []
    for w in root.findall("worksheets/worksheet"):
        if _attr(w, "name") not in placed:
            continue
        s = Sheet(_attr(w, "name"), placed[_attr(w, "name")])
        shelves = " ".join(w.findtext(f"table/{t}") or "" for t in ("rows", "cols"))
        encodings = " ".join(_attr(e, "column") for e in w.findall(".//encodings/*"))
        for ds, inner in _TOKEN.findall(f"{shelves} {encodings}"):
            s.datasource = s.datasource or str(ds_caption.get(ds) or ds)
            kind, label, formula = _classify(ds, inner, columns)
            if kind == "dim" and label not in s.shelf_dims:
                s.shelf_dims.append(label)
            elif kind == "measure":
                s.measures.setdefault(label, formula)
        for f in w.iter("filter"):
            if _attr(f, "column").endswith("[:Measure Names]"):
                # Measure Values: the sheet's measures are this filter's members.
                for g in f.iter("groupfilter"):
                    for ds, inner in _TOKEN.findall(_attr(g, "member")):
                        kind, label, formula = _classify(ds, inner, columns)
                        if kind == "measure":
                            s.measures.setdefault(label, formula)
                continue
            for ds, inner in _TOKEN.findall(_attr(f, "column")):
                kind, label, _ = _classify(ds, inner, columns)
                target = s.filter_dims if kind == "dim" else s.other_filters
                if label not in target and label not in s.shelf_dims:
                    target.append(label)
        sheets.append(s)
    return sheets


def propose_grains(sheets: list[Sheet], measure: str) -> list[list[str]]:
    """The total, each sheet's shelf grain, and each filter added to it one at a time."""
    grains: list[list[str]] = [[]]
    for s in sheets:
        if measure not in s.measures:
            continue
        for g in [s.shelf_dims] + [s.shelf_dims + [f] for f in s.filter_dims]:
            if g not in grains:
                grains.append(list(g))
    return grains


def _grains_command(a) -> int:
    sheets = parse_twb(a.twb, a.dashboard)
    if a.measure:
        using = [s for s in sheets if a.measure in s.measures]
        out = {
            "measure": a.measure,
            "sheets": [asdict(s) for s in using],
            "grains": propose_grains(sheets, a.measure),
        }
    else:
        out = {"sheets": [asdict(s) for s in sheets]}
    print(json.dumps(out, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grains", help="propose grains from a downloaded .twb")
    g.add_argument("twb")
    g.add_argument("--dashboard", action="append", required=True)
    g.add_argument("--measure")
    a = p.parse_args(argv)
    return _grains_command(a)


if __name__ == "__main__":
    sys.exit(main())
