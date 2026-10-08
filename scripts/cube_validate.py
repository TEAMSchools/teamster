"""Compare Cube with what a Tableau dashboard shows, at every grain its sheets use.

    uv run scripts/cube_validate.py grains <workbook.twb> --dashboard "<name>" [...] [--measure "<caption>"]
    uv run scripts/cube_validate.py run <checks.yml> [--rows <gid,...>] [--scope-only]

`grains` reads a downloaded .twb and proposes the grains for one measure's check entry.
`run` needs CUBE_API_SECRET, which only the pytest secrets fixture provides, so it runs
inside a throwaway tests/test_zz_*.py. Runbook: .claude/skills/cube-dashboard/SKILL.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import defusedxml.ElementTree as SafeET
import yaml

if TYPE_CHECKING:
    # trunk-ignore(bandit/B405): type-only import; parsing goes through defusedxml
    import xml.etree.ElementTree as ET

# [federated.<datasource>].[<derivation>:<field>:<type>], or [federated.<ds>].[<named filter>]
_TOKEN = re.compile(r"\[(federated\.[^\]]+)\]\.\[([^\]]+)\]")
# [<derivation>:<field>:<type>], with a trailing :N on quick table calculations
_INSTANCE = re.compile(r"^([a-z]+):(.+):([a-z]+)(?::\d+)?$")
# A quick table calculation wraps a measure: pcto:sum:<field>
_NESTED = re.compile(r"^([a-z]+):(.+)$")
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
class Construct:
    """A Tableau feature on a sheet that can change what the sheet shows."""

    kind: str
    name: str
    sheets: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.kind}: {self.name}"


CONSTRUCT_KINDS = {
    "group",
    "bin",
    "set",
    "viewer_function",
    "lod",
    "table_calc",
    "filter",
    "total",
    "alias",
    "fiscal_year",
    "parameter",
    "blend",
    "top_n",
    "source_filter",
}
_USER = "{http://www.tableausoftware.com/xml/user}"
_REF = re.compile(r"\[([^\[\]]+)\]")
_PARAM_REF = re.compile(r"\[Parameters\]\.\[[^\[\]]+\]")
_VIEWER = re.compile(r"\b(ISMEMBEROF|USERNAME|USERDOMAIN|FULLNAME)\s*\(", re.I)
_TABLE_CALC_FN = re.compile(
    r"\b(WINDOW_\w+|RUNNING_\w+|LOOKUP|INDEX|RANK\w*|TOTAL|SIZE|FIRST|LAST"
    r"|PREVIOUS_VALUE)\s*\(",
    re.I,
)
_DATE_FN = re.compile(r"\b(YEAR|QUARTER|DATEPART|DATETRUNC|DATENAME)\s*\(", re.I)
_LOD = re.compile(r"\{\s*(FIXED|INCLUDE|EXCLUDE)\b", re.I)
_PARAM_CASE = re.compile(
    r"^\s*CASE\s+\[Parameters\]\.\[([^\[\]]+)\]\s+(.*?)\s*END\s*$", re.S | re.I
)
_WHEN = re.compile(
    r"WHEN\s+'([^']*)'\s+THEN\s+(.*?)(?=\s+WHEN\s+'|\s+ELSE\b|\s*$)", re.S | re.I
)
# Groups Tableau builds from a viewer's clicks: actions, tooltips, highlights.
_IGNORED_GROUPS = ("Action (", "Tooltip (", "Highlight (")


def _tableau_value(raw: str):
    """A member as the .twb writes it: "text", a number, true/false, or %null%."""
    if raw == "%null%":
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    for cast in (int, float):
        try:
            return cast(raw)
        except ValueError:
            pass
    return raw


class _Workbook:
    """The lookups construct detection needs, built once per workbook."""

    def __init__(self, root: ET.Element):
        self.columns = _columns(root)
        self.cols: dict[tuple[str, str], ET.Element] = {}
        self.groups: dict[tuple[str, str], ET.Element] = {}
        self.drill_paths: dict[str, list[list[str]]] = {}
        self.source_filters: dict[str, list[ET.Element]] = {}
        self.ds_caption: dict[str, str] = {}
        # (datasource, Measure Names member token) -> the alias shown for it
        self.mn_aliases: dict[tuple[str, str], str] = {}
        for ds in root.findall("datasources/datasource"):
            name = _attr(ds, "name")
            self.ds_caption[name] = _attr(ds, "caption") or name
            for col in ds.findall("column"):
                self.cols.setdefault((name, _attr(col, "name")), col)
                if _attr(col, "name") == "[:Measure Names]":
                    for a in col.findall("aliases/alias"):
                        self.mn_aliases[(name, _attr(a, "key").strip('"'))] = _attr(
                            a, "value"
                        ).strip()
            for g in ds.findall("group"):
                self.groups.setdefault((name, _attr(g, "name")), g)
            self.drill_paths[name] = [
                [f.text or "" for f in p.findall("field")]
                for p in ds.findall("drill-paths/drill-path")
            ]
            self.source_filters[name] = ds.findall("filter") + ds.findall(
                "extract//filter"
            )

    def calc(self, ds: str, name: str):
        col = self.cols.get((ds, name))
        return col.find("calculation") if col is not None else None

    def caption(self, ds: str, name: str) -> str:
        col = self.cols.get((ds, name))
        return (_attr(col, "caption") if col is not None else "") or name.strip("[]")

    def formula(self, ds: str, name: str) -> str:
        calc = self.calc(ds, name)
        return _attr(calc, "formula") if calc is not None else ""

    def deps(self, ds: str, name: str) -> list[str]:
        """The fields a field's formula or group reads, as '[name]'."""
        calc = self.calc(ds, name)
        if calc is None:
            return []
        refs = _REF.findall(_PARAM_REF.sub("", _attr(calc, "formula")))
        out = [f"[{r}]" for r in refs]
        if calc.get("column"):
            out.append(_attr(calc, "column"))
        return out

    def closure(self, ds: str, names: list[str]) -> list[str]:
        """The fields named, and every field they read, transitively."""
        seen: list[str] = []
        todo = list(names)
        while todo:
            n = todo.pop(0)
            if n not in seen:
                seen.append(n)
                todo += self.deps(ds, n)
        return seen


def _bins(calc: ET.Element) -> dict:
    return {
        _tableau_value(_attr(b, "value")): [
            _tableau_value(v.text or "") for v in b.findall("value")
        ]
        for b in calc.findall("bin")
    }


def _param_branches(columns, ds: str, formula: str) -> dict | None:
    """A CASE on a parameter whose branches are fields or text, else None."""
    m = _PARAM_CASE.match(formula or "")
    if not m:
        return None
    branches: dict[str, str | None] = {}
    for value, expr in _WHEN.findall(m.group(2)):
        expr = expr.strip()
        ref = re.fullmatch(r"\[([^\[\]]+)\]", expr)
        if ref:
            branches[value] = _resolve(columns, ds, ref.group(1))[0]
        elif re.fullmatch(r"'[^']*'|\"[^\"]*\"", expr):
            branches[value] = None
        else:
            return None
    return {"parameter": m.group(1), "branches": branches} if branches else None


def _fiscal_start(book: _Workbook, ds: str, name: str) -> int | None:
    col = book.cols.get((ds, name))
    start = _attr(col, "fiscal-year-start") if col is not None else ""
    return int(start) if start and start != "1" else None


def _field_constructs(book: _Workbook, ds: str, name: str) -> list[Construct]:
    """Constructs one field carries: a group, a bin, an LOD, a viewer function..."""
    calc = book.calc(ds, name)
    if calc is None:
        return []
    caption, f = book.caption(ds, name), _attr(calc, "formula")
    out = []
    if calc.get("class") == "categorical-bin":
        src = _attr(calc, "column")
        src_formula = book.formula(ds, src)
        out.append(
            Construct(
                "group",
                caption,
                detail={
                    "of": None if src_formula else src.strip("[]"),
                    "of_formula": src_formula or None,
                    "bins": _bins(calc),
                },
            )
        )
        return out
    if calc.get("class") == "bin":
        src = (_REF.findall(f) or [""])[0]
        size = _tableau_value(_attr(calc, "size"))
        return [Construct("bin", caption, detail={"of": src, "size": size})]
    if lod := _LOD.search(f):
        out.append(
            Construct(
                "lod", caption, detail={"type": lod.group(1).lower(), "formula": f}
            )
        )
    if _VIEWER.search(f):
        out.append(Construct("viewer_function", caption, detail={"formula": f}))
    if _TABLE_CALC_FN.search(f) or calc.find("table-calc") is not None:
        out.append(Construct("table_calc", caption, detail={"formula": f}))
    if "[Parameters]." in f and _param_branches(book.columns, ds, f) is None:
        out.append(Construct("parameter", caption, detail={"formula": f}))
    if _DATE_FN.search(f) and any(
        _fiscal_start(book, ds, d) for d in book.deps(ds, name)
    ):
        out.append(Construct("fiscal_year", caption, detail={"formula": f}))
    return out


def _sheet_tokens(w: ET.Element) -> list[tuple[str, str]]:
    """Every field token a sheet uses: shelves, marks, filters, Measure Values."""
    parts = [w.findtext("table/rows") or "", w.findtext("table/cols") or ""]
    parts += [_attr(e, "column") for e in w.findall(".//encodings/*")]
    for f in w.iter("filter"):
        parts.append(_attr(f, "column"))
        if _attr(f, "column").endswith("[:Measure Names]"):
            parts += [_attr(g, "member") for g in f.iter("groupfilter")]
    return _TOKEN.findall(" ".join(parts))


def _filter_detail(f: ET.Element) -> dict | None:
    """What a filter keeps, or None for an all-values quick filter."""
    gfs = list(f.iter("groupfilter"))
    members = [
        _tableau_value(_attr(g, "member"))
        for g in gfs
        if _attr(g, "function") == "member"
    ]
    exclude = any(
        _attr(g, "function") == "except"
        or g.get(f"{_USER}ui-enumeration") == "exclusive"
        for g in gfs
    )
    rng = {k: f.findtext(k) for k in ("min", "max") if f.find(k) is not None}
    context = _attr(f, "context") == "true"
    if not (members or rng or context or _attr(f, "class") == "relative-date"):
        return None
    return {
        "mode": "exclude" if exclude else "include",
        "members": members,
        "nulls": None in members,
        "range": rng,
        "context": context,
        "class": _attr(f, "class"),
    }


def _set_construct(book: _Workbook, ds: str, name: str) -> Construct | None:
    """A set or user filter used on the sheet; action and tooltip groups are not."""
    g = book.groups.get((ds, f"[{name}]"))
    if g is None or name.startswith(_IGNORED_GROUPS):
        return None
    caption = _attr(g, "caption") or name
    gfs = list(g.iter("groupfilter"))
    exprs = [_attr(x, "expression") for x in gfs if x.get("expression")]
    if g.get(f"{_USER}ui-builder") == "identity-set" or any(
        _VIEWER.search(e) for e in exprs
    ):
        return Construct(
            "viewer_function", caption, detail={"set": name, "expressions": exprs}
        )
    return Construct(
        "set",
        caption,
        detail={
            "mode": "exclude"
            if any(_attr(x, "function") == "except" for x in gfs)
            else "include",
            "members": [
                _tableau_value(_attr(x, "member"))
                for x in gfs
                if _attr(x, "function") == "member"
            ],
            "of": next(
                (_attr(x, "level").strip("[]") for x in gfs if x.get("level")), None
            ),
        },
    )


def _measure_aliases(book: _Workbook, w: ET.Element, columns) -> dict[str, str]:
    """Measures this sheet shows through Measure Names under another name."""
    out = {}
    for f in w.iter("filter"):
        if not _attr(f, "column").endswith("[:Measure Names]"):
            continue
        for g in f.iter("groupfilter"):
            member = _attr(g, "member").strip('"')
            for ds, inner in _TOKEN.findall(member):
                alias = book.mn_aliases.get((ds, member))
                caption = _classify(ds, inner, columns)[1]
                if alias and alias != caption:
                    out[alias] = caption
    return out


def _sheet_constructs(book: _Workbook, w: ET.Element, columns) -> list[Construct]:
    """Every construct that can change what this sheet shows."""
    found: dict[str, Construct] = {}

    def add(c: Construct | None) -> None:
        if c is not None:
            found.setdefault(c.key, c)

    tokens = _sheet_tokens(w)
    instances = {_attr(ci, "name"): ci for ci in w.iter("column-instance")}
    by_ds: dict[str, list[str]] = {}
    for ds, inner in tokens:
        add(_set_construct(book, ds, inner))
        m = _INSTANCE.match(inner)
        if not m:
            continue
        deriv, fld, _ = m.groups()
        add(_set_construct(book, ds, fld))
        wrapped = _NESTED.match(fld)
        if wrapped and wrapped.group(1) in _MEASURE_DERIVATIONS:
            fld = wrapped.group(2)
            ci = instances.get(f"[{inner}]")
            tc = ci.find("table-calc") if ci is not None else None
            quick = _attr(tc, "type") if tc is not None else deriv
            add(
                Construct(
                    "table_calc",
                    _classify(ds, inner, columns)[1],
                    detail={"quick": quick or deriv},
                )
            )
        by_ds.setdefault(ds, []).append(f"[{fld}]")
        start = _fiscal_start(book, ds, f"[{fld}]")
        if deriv in ("yr", "tyr", "qr", "tqr") and start:
            add(
                Construct(
                    "fiscal_year",
                    _classify(ds, inner, columns)[1],
                    detail={"start_month": start},
                )
            )
    for f in w.iter("filter"):
        if _attr(f, "column").endswith("[:Measure Names]"):
            continue
        for ds, inner in _TOKEN.findall(_attr(f, "column")):
            if (ds, f"[{inner}]") in book.groups:
                continue  # a set: added from the tokens above
            label = _classify(ds, inner, columns)[1]
            if any(_attr(g, "function") == "end" for g in f.iter("groupfilter")):
                add(Construct("top_n", label))
            elif detail := _filter_detail(f):
                add(Construct("filter", label, detail=detail))
    sub = w.find("table/subtotals")
    # Plain subtotals become grains; any other setting needs a person to read it.
    if sub is not None and (sub.attrib or any(c.tag != "column" for c in sub)):
        add(
            Construct(
                "total",
                "subtotals",
                detail={
                    "attributes": dict(sub.attrib),
                    "children": [c.tag for c in sub],
                },
            )
        )
    used = list(
        dict.fromkeys(
            [ds for ds, _ in tokens]
            + [_attr(d, "datasource") for d in w.iter("datasource-dependencies")]
        )
    )
    used = [ds for ds in used if ds and ds != "Parameters"]
    for ds in used:
        if used and ds != used[0]:
            add(Construct("blend", book.ds_caption.get(ds, ds)))
        for f in book.source_filters.get(ds, []):
            for fds, inner in _TOKEN.findall(_attr(f, "column")):
                label = _classify(fds, inner, columns)[1]
                add(
                    Construct(
                        "source_filter",
                        f"{book.ds_caption.get(ds, ds)}: {label}",
                        detail=_filter_detail(f) or {},
                    )
                )
    for alias, caption in _measure_aliases(book, w, columns).items():
        add(Construct("alias", alias, detail={"field": caption}))
    for ds, names in by_ds.items():
        for n in book.closure(ds, names):
            for c in _field_constructs(book, ds, n):
                add(c)
    return list(found.values())


@dataclass
class Sheet:
    name: str
    dashboards: list[str]
    datasource: str = ""
    measures: dict[str, str] = field(default_factory=dict)  # caption -> formula
    shelf_dims: list[str] = field(default_factory=list)
    filter_dims: list[str] = field(default_factory=list)
    other_filters: list[str] = field(default_factory=list)
    rows_dims: list[str] = field(default_factory=list)
    cols_dims: list[str] = field(default_factory=list)
    # A measure shown through Measure Names under another name: alias -> caption.
    measure_aliases: dict[str, str] = field(default_factory=dict)
    # Dimension label -> {parameter, branches: {parameter value: label or None}}.
    param_dims: dict[str, dict] = field(default_factory=dict)
    drill_paths: list[list[str]] = field(default_factory=list)
    subtotal_dims: list[str] = field(default_factory=list)
    constructs: list[Construct] = field(default_factory=list)


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
                _attr(calc, "formula")
                if calc is not None and calc.get("class", "tableau") == "tableau"
                else "",
            )
    return out


def _resolve(columns, ds: str, fld: str) -> tuple[str, str]:
    """Caption and formula of a field, following plain copies ([x]) to their source."""
    caption, formula = columns.get((ds, f"[{fld}]"), (fld, ""))
    for _ in range(5):
        src = re.fullmatch(r"\s*\[([^\[\]]+)\]\s*", formula or "")
        if not src:
            break
        caption, formula = columns.get((ds, f"[{src.group(1)}]"), (src.group(1), ""))
    return caption, formula


def _classify(ds: str, inner: str, columns) -> tuple[str, str, str]:
    """Return (kind, label, formula); kind is 'dim', 'measure' or 'other'."""
    m = _INSTANCE.match(inner)
    if not m:
        return "other", inner, ""
    deriv, fld, _ = m.groups()
    wrapped = _NESTED.match(fld)
    if wrapped and wrapped.group(1) in _MEASURE_DERIVATIONS:
        deriv, fld = wrapped.groups()
    caption, formula = _resolve(columns, ds, fld)
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
    book = _Workbook(root)
    columns = book.columns
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

        raw: list[str] = []

        def take(text: str, dims: list[str], s=s, raw=raw) -> None:
            for ds, inner in _TOKEN.findall(text):
                s.datasource = s.datasource or str(ds_caption.get(ds) or ds)
                if ds not in raw:
                    raw.append(ds)
                kind, label, formula = _classify(ds, inner, columns)
                branches = _param_branches(columns, ds, formula)
                if kind == "dim" and label not in dims:
                    dims.append(label)
                    if branches:
                        s.param_dims[label] = branches
                elif kind == "measure":
                    s.measures.setdefault(label, formula)
                    # A parameter that swaps measures: the sheet shows each branch.
                    for b in (branches or {}).get("branches", {}).values():
                        if b:
                            s.measures.setdefault(b, "")

        take(w.findtext("table/rows") or "", s.rows_dims)
        take(w.findtext("table/cols") or "", s.cols_dims)
        s.shelf_dims = list(dict.fromkeys(s.rows_dims + s.cols_dims))
        take(
            " ".join(_attr(e, "column") for e in w.findall(".//encodings/*")),
            s.shelf_dims,
        )
        for ds in raw:
            for path in book.drill_paths.get(ds, []):
                labels = [_resolve(columns, ds, n.strip("[]"))[0] for n in path]
                if any(d in s.shelf_dims for d in labels):
                    s.drill_paths.append(labels)
        for ds, inner in _TOKEN.findall(
            " ".join(c.text or "" for c in w.findall("table/subtotals/column"))
        ):
            s.subtotal_dims.append(_classify(ds, inner, columns)[1])
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
        s.measure_aliases = _measure_aliases(book, w, columns)
        s.constructs = _sheet_constructs(book, w, columns)
        sheets.append(s)
    return sheets


def _dedupe(dims) -> list[str]:
    return list(dict.fromkeys(d for d in dims if d is not None))


def _shelves(s: Sheet) -> list[list[str]]:
    """The sheet's shelf grain once per parameter value and per drill level."""
    shelves = [list(s.shelf_dims)]
    by_param: dict[str, list[str]] = {}
    for label, p in s.param_dims.items():
        by_param.setdefault(p["parameter"], []).append(label)
    for labels in by_param.values():
        # Every field switching on one parameter switches together.
        values = list(
            dict.fromkeys(v for lb in labels for v in s.param_dims[lb]["branches"])
        )
        shelves = [
            _dedupe(
                s.param_dims[d]["branches"].get(v) if d in labels else d for d in shelf
            )
            for shelf in shelves
            for v in values
        ]
    for path in s.drill_paths:
        nxt = []
        for shelf in shelves:
            at = [i for i, d in enumerate(shelf) if d in path]
            if not at:
                nxt.append(shelf)
                continue
            rest = [d for d in shelf if d not in path]
            pos = sum(1 for d in shelf[: at[0]] if d not in path)
            nxt += [rest[:pos] + path[:k] + rest[pos:] for k in range(1, len(path) + 1)]
        shelves = nxt
    return [list(t) for t in dict.fromkeys(tuple(sh) for sh in shelves)]


def _subtotal_grains(s: Sheet, shelf: list[str]) -> list[list[str]]:
    """A subtotal on d totals the fields nested inside d on its axis."""
    out = []
    for d in s.subtotal_dims:
        axis = s.rows_dims if d in s.rows_dims else s.cols_dims
        if d in shelf and d in axis:
            inner = axis[axis.index(d) + 1 :]
            out.append([x for x in shelf if x not in inner])
    return out


def propose_grains(sheets: list[Sheet], measure: str) -> list[list[str]]:
    """The total; each sheet's shelf grains, subtotals, and each filter added."""
    grains: list[list[str]] = [[]]
    for s in sheets:
        if measure not in s.measures and measure not in s.measure_aliases:
            continue
        for shelf in _shelves(s):
            extra = [shelf + [f] for f in s.filter_dims if f not in shelf]
            for g in [shelf] + _subtotal_grains(s, shelf) + extra:
                if g not in grains:
                    grains.append(list(g))
    return grains


def merge_constructs(sheets: list[Sheet]) -> list[Construct]:
    """Each construct once, with every sheet it appears on."""
    out: dict[str, Construct] = {}
    for s in sheets:
        for c in s.constructs:
            m = out.setdefault(c.key, Construct(c.kind, c.name, [], c.detail))
            if s.name not in m.sheets:
                m.sheets.append(s.name)
    return list(out.values())


def audit_rows(checks: dict, twb) -> dict[str, dict]:
    """Per row: constructs on its sheets, split into not checked and unaccounted."""
    rows = [str(r["row_gid"]) for r in checks["rows"]]
    if not checks["dashboards"]:
        msg = "the checks file names no dashboards, so its sheets cannot be audited"
        return {gid: {"error": msg} for gid in rows}
    sheets = parse_twb(twb, checks["dashboards"])
    out = {}
    for row in checks["rows"]:
        gid = str(row["row_gid"])
        captions = [c for m in row["metrics"] for c in m["tableau"]]
        if not captions:
            out[gid] = {
                "error": "no metric names its Tableau measure (tableau:), so its "
                "sheets cannot be audited"
            }
            continue
        using = [
            s
            for s in sheets
            if any(c in s.measures or c in s.measure_aliases for c in captions)
        ]
        if not using:
            out[gid] = {
                "error": f"no sheet on {', '.join(checks['dashboards'])} shows "
                f"{', '.join(captions)}"
            }
            continue
        why = {n["construct"]: n["why"] for n in row["not_checked"]}
        found = merge_constructs(using)
        out[gid] = {
            "not_checked": [
                dict(asdict(c), key=c.key, why=why[c.key])
                for c in found
                if c.key in why
            ],
            "unaccounted": [
                dict(asdict(c), key=c.key)
                for c in found
                if c.key not in why and c.key not in checks["handled"]
            ],
        }
    return out


# ---------------------------------------------------------------- checks files and queries
CUBE_LIMIT = 50_000
# An average is a rate on its own scale (a scale score): compared in its units.
KINDS = {"count", "rate", "average"}


class CheckError(ValueError):
    """A checks file that cannot be run as written."""


@dataclass(frozen=True)
class Dim:
    name: str
    cube: str | None  # None: no Cube member, so grains using it are not comparable
    sql: str
    granularity: str | None = None
    tableau_only: bool = False  # a dashboard control, not data: never a missing member
    group_kind: str | None = (
        None  # a Tableau group: relabel (buckets) or rule (a definition)
    )


def group_case_sql(of: str, bins: dict, other: str | None = None) -> str:
    """A Tableau group as SQL; a value in no bin keeps its own value unless `other`."""
    whens = []
    for label, values in bins.items():
        conds = []
        kept = [v for v in values if v is not None]
        if kept:
            conds.append(f"{of} in ({', '.join(_sql_literal(v) for v in kept)})")
        if any(v is None for v in values):
            conds.append(f"{of} is null")
        whens.append(f"when {' or '.join(conds)} then {_sql_literal(label)}")
    # The kept value is cast so a numeric field still matches text bin labels.
    rest = _sql_literal(other) if other is not None else f"cast({of} as string)"
    return f"case {' '.join(whens)} else {rest} end"


def _dim_sql(path, name: str, d: dict) -> str:
    if "group" in d:
        if "sql" in d:
            raise CheckError(f"{path}: dimension '{name}': give group or sql, not both")
        if d.get("kind") not in ("relabel", "rule"):
            raise CheckError(
                f"{path}: dimension '{name}': a group needs kind relabel or rule"
            )
        g = d["group"]
        return group_case_sql(g["of"], g["bins"], g.get("other"))
    if "bin" in d:
        b = d["bin"]
        return f"floor(({b['of']}) / {b['size']}) * {b['size']}"
    if "sql" not in d:
        raise CheckError(f"{path}: dimension '{name}' needs sql, group or bin")
    return d["sql"]


def _construct_key_ok(key) -> bool:
    kind, _, name = str(key).partition(": ")
    return kind in CONSTRUCT_KINDS and bool(name)


def load_checks(path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    for key in (
        "dashboard",
        "extract",
        "cube_source_table",
        "view",
        "dimensions",
        "rows",
    ):
        if key not in data:
            raise CheckError(f"{path}: missing '{key}'")
    for key in ("workbook_luid", "datasource"):
        if not data["extract"].get(key):
            raise CheckError(f"{path}: extract needs '{key}'")
    dims = {
        n: Dim(
            n,
            d.get("cube"),
            _dim_sql(path, n, d),
            d.get("granularity"),
            bool(d.get("tableau_only")),
            d.get("kind") if ("group" in d or "bin" in d) else None,
        )
        for n, d in data["dimensions"].items()
    }
    window = data.get("window")
    if window is not None:
        # An academic-year window (state tests are scored by year, not by day).
        years = window.get("academic_years") if isinstance(window, dict) else None
        if not years or not all(isinstance(y, int) for y in years):
            raise CheckError(f"{path}: window needs a list of academic_years")
        if not dims.get("academic_year") or not dims["academic_year"].cube:
            raise CheckError(
                f"{path}: an academic-year window needs an academic_year dimension"
            )
    elif "date" not in dims or not dims["date"].cube:
        raise CheckError(
            f"{path}: 'dimensions.date' needs a cube member and a sql column"
        )
    for d in dims.values():
        if d.granularity and ("date" not in dims or d.cube != dims["date"].cube):
            raise CheckError(
                f"{path}: dimension '{d.name}' has a granularity but is not on the "
                f"date member '{dims['date'].cube}'"
            )
    data.setdefault("hard_filters", [])
    for f in data["hard_filters"]:
        if f["dim"] not in dims:
            raise CheckError(f"{path}: hard filter on unknown dimension '{f['dim']}'")
    for row in data["rows"]:
        where = f"{path}: row {row.get('row_gid')} ({row.get('name')})"
        for key in ("row_gid", "name", "metrics", "grains"):
            if key not in row:
                raise CheckError(f"{where}: missing '{key}'")
        for m in row["metrics"]:
            if m.get("kind") not in KINDS:
                raise CheckError(
                    f"{where}: metric {m.get('cube')}: kind must be count or rate"
                )
            need = ("cube", "sql") if m["kind"] == "count" else ("cube", "num", "den")
            missing = [k for k in need if not m.get(k)]
            if missing:
                raise CheckError(
                    f"{where}: metric {m.get('cube')} is missing {missing}"
                )
            diag = m.get("diagnose_by")
            if diag is not None and not (
                isinstance(diag, dict) and diag.get("cube") and diag.get("sql")
            ):
                raise CheckError(
                    f"{where}: metric {m.get('cube')}: diagnose_by needs cube and sql"
                )
            if m.get("missing_members"):
                need = (
                    ("sql_without",)
                    if m["kind"] == "count"
                    else ("num_without", "den_without")
                )
                missing = [k for k in need if not m.get(k)]
                if missing:
                    raise CheckError(
                        f"{where}: metric {m.get('cube')} lists missing_members, so "
                        f"it needs {missing}: the same SQL without the missing field"
                    )
        for m in row["metrics"]:
            t = m.get("tableau")
            m["tableau"] = [t] if isinstance(t, str) else list(t or [])
        row.setdefault("not_checked", [])
        for n in row["not_checked"]:
            if not _construct_key_ok(n.get("construct")):
                raise CheckError(
                    f"{where}: not_checked names unknown construct "
                    f"'{n.get('construct')}' (use '<kind>: <name>' from `grains`)"
                )
            if not n.get("why"):
                raise CheckError(f"{where}: not_checked '{n['construct']}' needs a why")
        for g in row["grains"]:
            unknown = [n for n in g if n not in dims]
            if unknown:
                raise CheckError(
                    f"{where}: grain {g} uses unknown dimension(s) {unknown}"
                )
            if sum(1 for n in g if dims[n].granularity) > 1:
                raise CheckError(f"{where}: grain {g} has more than one date part")
    data["dashboards"] = list(data.get("dashboards") or [])
    data["handled"] = dict(data.get("handled") or {})
    for key in data["handled"]:
        if not _construct_key_ok(key):
            raise CheckError(f"{path}: handled names unknown construct '{key}'")
    seen: dict[str, dict] = {}
    for row in data["rows"]:
        for m in row["metrics"]:
            first = seen.setdefault(m["cube"], m)
            if first != m:
                raise CheckError(
                    f"{path}: metric {m['cube']} is defined twice with different "
                    "SQL; rows that share a Cube member must share its definition"
                )
    data["dimensions"] = dims
    # Cube-side only: what the dashboard's table already excludes (e.g. break days).
    data.setdefault("cube_filters", [])
    # Extract-side only: rows the dashboard's table holds that Cube never carries.
    data.setdefault("truth_filters", [])
    data.setdefault("scope_measure", "count_students")
    data.setdefault("students_sql", "count(distinct student_number)")
    return data


def academic_window(today: dt.date) -> tuple[dt.date, dt.date]:
    """July 1 of the academic year that contains yesterday, through yesterday."""
    end = today - dt.timedelta(days=1)
    return dt.date(end.year if end.month >= 7 else end.year - 1, 7, 1), end


def resolve_window(checks: dict, today: dt.date):
    """The checks file's academic-year window, or July 1 through yesterday."""
    if checks.get("window"):
        return {"academic_years": sorted(checks["window"]["academic_years"])}
    return academic_window(today)


def _window_label(window) -> list[str]:
    if isinstance(window, dict):
        years = window["academic_years"]
        return [f"{y}-{str(y + 1)[-2:]}" for y in (years[0], years[-1])]
    return [window[0].isoformat(), window[1].isoformat()]


def cube_key(view: str, dim: Dim) -> str:
    return (
        f"{view}.{dim.cube}.{dim.granularity}"
        if dim.granularity
        else f"{view}.{dim.cube}"
    )


def cube_query(
    view, measures, grain, dims, hard_filters, window, cube_filters=()
) -> dict:
    by_year = isinstance(window, dict)
    td: dict = {"dimension": f"{view}.{dims['date'].cube}"} if "date" in dims else {}
    if not by_year:
        td["dateRange"] = [window[0].isoformat(), window[1].isoformat()]
    plain = []
    for name in grain:
        d = dims[name]
        if d.granularity:
            td["granularity"] = d.granularity
        else:
            plain.append(f"{view}.{d.cube}")
    year_filter = (
        [
            {
                "member": f"{view}.{dims['academic_year'].cube}",
                "operator": "equals",
                "values": [str(y) for y in window["academic_years"]],
            }
        ]
        if by_year
        else []
    )
    return {
        "measures": [f"{view}.{m}" for m in measures],
        "dimensions": plain,
        "timeDimensions": [td] if not by_year or "granularity" in td else [],
        "filters": year_filter
        + [
            {
                "member": f"{view}.{dims[f['dim']].cube}",
                "operator": "equals",
                "values": [str(v) for v in f["values"]],
            }
            for f in hard_filters
        ]
        + [dict(f, member=f"{view}.{f['member']}") for f in cube_filters],
        "limit": CUBE_LIMIT,
        "timezone": "UTC",
    }


def _sql_literal(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v)
    return "'" + str(v).replace("'", "\\'") + "'"


def truth_sql(
    table, metrics, grain, dims, hard_filters, window, students_sql, truth_filters=()
) -> str:
    select = [f"{dims[n].sql} as g{i}" for i, n in enumerate(grain)]
    for i, m in enumerate(metrics):
        if m["kind"] == "count":
            select.append(f"{m['sql']} as m{i}")
        else:
            select += [f"{m['num']} as m{i}_num", f"{m['den']} as m{i}_den"]
        if m.get("missing_members") and m["kind"] == "count":
            select.append(f"{m['sql_without']} as m{i}_alt")
        elif m.get("missing_members"):
            select += [
                f"{m['num_without']} as m{i}_alt_num",
                f"{m['den_without']} as m{i}_alt_den",
            ]
    select.append(f"{students_sql} as n_students")
    if isinstance(window, dict):
        years = ", ".join(str(y) for y in window["academic_years"])
        where = [f"{dims['academic_year'].sql} in ({years})"]
    else:
        where = [f"{dims['date'].sql} between '{window[0]}' and '{window[1]}'"]
    for f in hard_filters:
        values = ", ".join(_sql_literal(v) for v in f["values"])
        where.append(f"{dims[f['dim']].sql} in ({values})")
    where += list(truth_filters)
    # trunk-ignore(bandit/B608): SQL comes from a reviewed checks file and runs read-only
    sql = f"select {', '.join(select)} from `{table}` where {' and '.join(where)}"
    if grain:
        sql += " group by " + ", ".join(str(i + 1) for i in range(len(grain)))
    return sql


# ---------------------------------------------------------------- comparison
SMALL_CELL = 10
# Rates within 0.1 percentage point; averages within 0.1 of their units.
TOLERANCE = {"rate": 0.001, "average": 0.1}
# The smallest gap that shows at display precision.
SHOWN = {"rate": 0.0005, "average": 0.05, "count": 0.5}
_ISO_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ]")
_WHOLE_FLOAT = re.compile(r"^-?\d+\.0+$")


def norm_key(v) -> str:
    """One spelling per dimension value, so Cube strings join BigQuery types."""
    if v is None:
        return "∅"
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, dt.date):
        return v.isoformat()[:10]
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = str(v).strip()
    if m := _ISO_DATE.match(s):
        return m.group(1)
    if _WHOLE_FLOAT.match(s):
        return s.split(".")[0]
    if s in ("True", "False"):
        return s.lower()
    return s


def _num(v) -> float | None:
    return None if v is None or v == "" else float(v)


@dataclass
class Cell:
    key: tuple[str, ...]
    cube: float | None
    truth: float | None
    n_students: int | None
    ok: bool
    explained: bool = False  # fails, but matches the variant without a missing member

    @property
    def delta(self) -> float:
        if self.cube is None or self.truth is None:
            return float("inf")
        return abs(self.cube - self.truth)


def cube_cells(rows, view, grain_dims, metric) -> dict:
    keys = [cube_key(view, d) for d in grain_dims]
    return {
        tuple(norm_key(r.get(k)) for k in keys): _num(r.get(f"{view}.{metric}"))
        for r in rows
    }


def truth_cells(rows, n_grain, i, kind, suffix="") -> dict:
    out = {}
    for r in rows:
        key = tuple(norm_key(r[f"g{j}"]) for j in range(n_grain))
        if kind == "count":
            v = _num(r[f"m{i}{suffix}"])
        else:
            num, den = _num(r[f"m{i}{suffix}_num"]), _num(r[f"m{i}{suffix}_den"])
            v = None if not den else (num or 0.0) / den
        n = r.get("n_students")
        out[key] = (v, None if n is None else int(n))
    return out


def _matches(kind, c, t) -> bool:
    if kind == "count":
        # No row on a side means nothing to count there: compare as 0.
        return abs((c or 0.0) - (t or 0.0)) < 1e-9
    return (c is None and t is None) or (
        c is not None and t is not None and abs(c - t) <= TOLERANCE[kind] + 1e-12
    )


def compare(kind, cube, truth) -> list[Cell]:
    cells = []
    for key in sorted(set(cube) | set(truth)):
        c = cube.get(key)
        t, n = truth.get(key, (None, None))
        if kind == "count":
            c, t = c or 0.0, t or 0.0
        cells.append(Cell(key, c, t, n, _matches(kind, c, t)))
    return cells


def explain(cells, kind, without) -> None:
    """Mark failed cells that match the truth computed without a missing member."""
    for c in cells:
        if not c.ok:
            c.explained = _matches(kind, c.cube, without.get(c.key, (None, None))[0])


def summarize(cells, kind, without=None) -> dict:
    bad = sorted(
        (c for c in cells if not c.ok and not c.explained), key=lambda c: -c.delta
    )
    only = None
    if len(cells) == 1:
        only = {"cube": cells[0].cube, "truth": cells[0].truth}
        if without is not None:
            only["without"] = without.get(cells[0].key, (None, None))[0]
    return {
        "cells": len(cells),
        "bad": len(bad),
        "explained": sum(1 for c in cells if c.explained),
        "only": only,
        "worst": [
            {
                "key": list(c.key),
                "cube": c.cube,
                "truth": c.truth,
                "n_students": c.n_students,
                "kind": kind,
            }
            for c in bad[:5]
        ],
    }


def row_verdict(grains) -> str:
    statuses = [g["status"] for g in grains]
    if "fail" in statuses:
        return "fail"
    if "error" in statuses:
        return "incomplete"
    if "missing_member" in statuses:
        return "missing_member"
    if "pass" not in statuses:
        return "incomplete"
    return "pass"


# ---------------------------------------------------------------- clients
DEFAULT_CUBE_URL = (
    "https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1"
)
USER_EMAIL_CACHE = Path.home() / ".config" / "teamster" / "cube-user-email"
DEFAULT_OUT = Path.home() / "asana-sync" / "validation"
BQ_PROJECT = "teamster-332318"


class CubeError(RuntimeError):
    """Cube returned an error, or a result that cannot be compared."""


class ScopeError(RuntimeError):
    """The Cube identity sees less than the dashboard does."""


class CubeClient:
    def __init__(self, url, secret, email, http=None, sleep=time.sleep):
        import httpx

        self.url, self.secret, self.email = url.rstrip("/"), secret, email
        self.http = http or httpx.Client(timeout=60)
        self.sleep = sleep

    def _token(self) -> str:
        import jwt

        now = int(time.time())
        # cube.js checks maxAge from `iat`, so it must be present.
        return jwt.encode(
            {"email": self.email, "iat": now, "exp": now + 300},
            self.secret,
            algorithm="HS256",
        )

    def load(self, query) -> tuple[list[dict], list[str]]:
        for _ in range(120):
            r = self.http.post(
                f"{self.url}/load",
                json={"query": query},
                headers={"Authorization": self._token()},
            )
            try:
                body = r.json()
            except ValueError as e:
                raise CubeError(f"HTTP {r.status_code}: response is not JSON") from e
            if body.get("error") == "Continue wait":
                self.sleep(1)
                continue
            if r.status_code >= 400 or "error" in body:
                raise CubeError(str(body.get("error") or f"HTTP {r.status_code}")[:300])
            rows = body.get("data", [])
            if len(rows) >= CUBE_LIMIT:
                raise CubeError(
                    f"result hit the {CUBE_LIMIT}-row limit; this grain is too fine"
                )
            return rows, sorted((body.get("usedPreAggregations") or {}).keys())
        raise CubeError("gave up after 120 'Continue wait' responses")


def bigquery_rows(sql: str) -> list[dict]:
    from google.cloud import bigquery

    return [
        dict(r.items()) for r in bigquery.Client(project=BQ_PROJECT).query(sql).result()
    ]


# ---------------------------------------------------------------- the dashboard's extract
EXTRACT_TABLE = "EXTRACT_TABLE"  # truth_sql's table; to_hyper_sql names the extract's
LOCAL_TZ = "America/New_York"
MAX_SNAPSHOT_GAP = dt.timedelta(minutes=60)
SCRATCH = Path(__file__).resolve().parents[1] / ".claude" / "scratch" / "cube-dashboard"


class TimingError(RuntimeError):
    """The extract and the Cube fact are snapshots from different times."""


def _extract_connection(twb, datasource: str):
    root = SafeET.parse(twb).getroot()
    if root is None:
        raise ValueError(f"{twb}: empty workbook")
    for d in root.findall("datasources/datasource"):
        if not _attr(d, "caption").startswith(datasource):
            continue
        for c in d.findall("extract/connection"):
            if c.get("class") == "hyper" and c.get("dbname"):
                return c
    raise CheckError(f"{twb}: no extract for datasource '{datasource}'")


def extract_file_name(twb, datasource: str) -> str:
    """The .hyper file name the workbook's datasource extract is stored under."""
    return Path(_attr(_extract_connection(twb, datasource), "dbname")).name


def extract_refresh_time(twb, datasource: str) -> dt.datetime | None:
    """When this datasource's extract last refreshed (Tableau stores it in UTC)."""
    raw = _attr(_extract_connection(twb, datasource), "update-time")
    if not raw:
        return None
    return dt.datetime.strptime(raw, "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=dt.UTC)


def to_hyper_sql(sql: str) -> str:
    """Translate check SQL from BigQuery to Hyper's PostgreSQL dialect."""
    import sqlglot

    out = sqlglot.transpile(sql, read="bigquery", write="postgres")[0]
    return out.replace(f'"{EXTRACT_TABLE}"', '"Extract"."Extract"')


def _py_value(v):
    for attr in ("to_datetime", "to_date"):
        if hasattr(v, attr):
            return getattr(v, attr)()
    return v


class ExtractSource:
    """Runs check SQL against one .hyper file; use as a context manager."""

    def __init__(self, path: Path):
        self.path = path

    def __enter__(self):
        # trunk-ignore(pyright/reportMissingImports): added per run with uv run --with
        from tableauhyperapi import Connection, HyperProcess, Telemetry

        self._hp = HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU)
        self._con = Connection(self._hp.endpoint, str(self.path))
        return self

    def __exit__(self, *exc):
        self._con.close()
        self._hp.close()

    def __call__(self, sql: str) -> list[dict]:
        with self._con.execute_query(to_hyper_sql(sql)) as result:
            names = [c.name.unescaped for c in result.schema.columns]
            return [
                {n: _py_value(v) for n, v in zip(names, row, strict=True)}
                for row in result
            ]


def retry(fn, attempts: int = 3, sleep=time.sleep, wait: float = 5.0):
    """Call fn until it succeeds; Tableau sign-ins fail transiently with 401002."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - re-raised after the last attempt
            if attempt == attempts:
                raise
            sleep(wait * attempt)
    raise ValueError("retry needs attempts >= 1")


def download_extract(
    luid: str, datasource: str, out_dir: Path
) -> tuple[Path, dt.datetime]:
    """Download the workbook with extracts; return the datasource's .hyper and refresh time."""
    import zipfile

    import tableauserverclient as tsc

    out_dir.mkdir(parents=True, exist_ok=True)
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)

    def fetch():
        # A fresh sign-in per attempt: the recovery for a 401002 sign-in race.
        with server.auth.sign_in(auth):
            refreshed = server.workbooks.get_by_id(luid).updated_at
            # tableauserverclient appends the extension: pass the stem.
            path = Path(
                server.workbooks.download(
                    luid, filepath=str(out_dir / "workbook"), include_extract=True
                )
            )
        return refreshed, path

    refreshed_at, twbx = retry(fetch)
    with zipfile.ZipFile(twbx) as z:
        twb = next(n for n in z.namelist() if n.endswith(".twb"))
        (out_dir / "workbook.twb").write_bytes(z.read(twb))
        name = extract_file_name(out_dir / "workbook.twb", datasource)
        member = next(n for n in z.namelist() if Path(n).name == name)
        hyper = out_dir / name
        hyper.write_bytes(z.read(member))
    # The datasource's own refresh time; the workbook's also moves on republish.
    refreshed_at = (
        extract_refresh_time(out_dir / "workbook.twb", datasource) or refreshed_at
    )
    if refreshed_at is None:
        raise TimingError(f"Tableau returned no refresh time for workbook {luid}")
    return hyper, refreshed_at


def cube_built_at(table: str, bq) -> dt.datetime:
    """When the Cube fact table was last rebuilt, from BigQuery's table metadata."""
    dataset, name = table.rsplit(".", 1)
    rows = bq(
        # trunk-ignore(bandit/B608): the table name comes from a reviewed checks file
        f"select last_modified_time from `{dataset}.__TABLES__` where table_id = '{name}'"
    )
    return dt.datetime.fromtimestamp(int(rows[0]["last_modified_time"]) / 1000, dt.UTC)


MODEL_DIR = Path(__file__).resolve().parents[1] / "src" / "cube" / "model" / "cubes"


def cube_definition(member: str, view: str, model_dir: Path = MODEL_DIR) -> dict | None:
    """A Cube measure's sql, type and filters, read from the cube YAML files."""

    def describe(m: dict) -> dict:
        return {
            "sql": str(m.get("sql", "")),
            "type": m.get("type", ""),
            "filters": [x["sql"] for x in m.get("filters", [])],
        }

    found = []
    for f in sorted(Path(model_dir).rglob("*.yml")):
        for cube in (yaml.safe_load(f.read_text()) or {}).get("cubes", []):
            measures = {m.get("name"): m for m in cube.get("measures", [])}
            if member not in measures:
                continue
            d = {"cube": cube["name"], **describe(measures[member])}
            # A derived measure's fix usually lands in a measure it uses.
            refs = [
                {"name": n, **describe(measures[n])}
                for n in dict.fromkeys(re.findall(r"\{(\w+)\}", d["sql"]))
                if n in measures
            ]
            if refs:
                d["refs"] = refs
            found.append(d)
    # Several cubes can share a measure name: prefer the one the view is named for.
    found.sort(key=lambda d: not view.startswith(d["cube"]))
    return found[0] if found else None


def _local(ts: dt.datetime) -> str:
    from zoneinfo import ZoneInfo

    return ts.astimezone(ZoneInfo(LOCAL_TZ)).strftime("%Y-%m-%d %H:%M ET")


def snapshot_date(ts: dt.datetime) -> dt.date:
    from zoneinfo import ZoneInfo

    return ts.astimezone(ZoneInfo(LOCAL_TZ)).date()


def timing_guard(extract_at: dt.datetime, cube_at: dt.datetime) -> None:
    gap = extract_at - cube_at
    if gap > MAX_SNAPSHOT_GAP:
        raise TimingError(
            f"The Cube fact was built {_local(cube_at)}, {gap} before the extract was "
            f"refreshed {_local(extract_at)}. Rerun after Cube's next build."
        )
    if -gap > MAX_SNAPSHOT_GAP:
        raise TimingError(
            f"The extract was refreshed {_local(extract_at)}, {-gap} before the Cube fact "
            f"was built {_local(cube_at)}. Rerun after the extract's next refresh."
        )


# ---------------------------------------------------------------- run
def _missing(missing: dict, name: str) -> dict:
    return missing.setdefault(
        name, {"explains_cells": 0, "blocks_grains": [], "changes_total": False}
    )


def reopen_for(row: dict) -> list[str]:
    """Missing members that cause part of a row's gap: the row is not shipped."""
    return sorted(
        n
        for n, m in row.get("missing_members", {}).items()
        if m["explains_cells"] or m.get("changes_total")
    )


def _diagnose(checks, cube_load, bq, window, view, metric) -> dict:
    """Break a failing metric's total down by its diagnostic field.

    A metric with missing members is broken down on its SQL without them, so the
    breakdown shows only the gaps the missing members do not explain.
    """
    by = metric["diagnose_by"]
    basis = None
    if metric.get("missing_members"):
        basis = f"without {', '.join(metric['missing_members'])}"
        keys = ("sql",) if metric["kind"] == "count" else ("num", "den")
        metric = {
            **{k: v for k, v in metric.items() if k != "missing_members"},
            **{k: metric[f"{k}_without"] for k in keys},
        }
    dims = {**checks["dimensions"], "_by": Dim("_by", by["cube"], by["sql"])}
    hard = checks["hard_filters"]
    try:
        crows, _ = cube_load(
            cube_query(
                view,
                [metric["cube"]],
                ["_by"],
                dims,
                hard,
                window,
                checks["cube_filters"],
            )
        )
        trows = bq(
            truth_sql(
                EXTRACT_TABLE,
                [metric],
                ["_by"],
                dims,
                hard,
                window,
                checks["students_sql"],
                checks["truth_filters"],
            )
        )
    except Exception as e:  # noqa: BLE001 - a missing breakdown never changes the verdict
        return {
            "by": by["cube"],
            "basis": basis,
            "cells": [],
            "error": f"{type(e).__name__}: {e}"[:300],
        }
    cells = compare(
        metric["kind"],
        cube_cells(crows, view, [dims["_by"]], metric["cube"]),
        truth_cells(trows, 1, 0, metric["kind"]),
    )
    bad = sorted((c for c in cells if not c.ok), key=lambda c: -c.delta)
    return {
        "by": by["cube"],
        "basis": basis,
        "cells": [
            {
                "value": c.key[0],
                "cube": c.cube,
                "truth": c.truth,
                "n_students": c.n_students,
            }
            for c in bad[:10]
        ],
    }


def scope_guard(checks, cube_load, bq, window) -> None:
    """Stop when Cube sees none of a hard-filter value the warehouse has students for."""
    if not checks["hard_filters"]:
        return
    view, dims, hard = checks["view"], checks["dimensions"], checks["hard_filters"]
    name = hard[0]["dim"]
    rows, _ = cube_load(
        cube_query(
            view,
            [checks["scope_measure"]],
            [name],
            dims,
            hard,
            window,
            checks["cube_filters"],
        )
    )
    seen = {
        norm_key(r.get(cube_key(view, dims[name]))): _num(
            r.get(f"{view}.{checks['scope_measure']}")
        )
        or 0
        for r in rows
    }
    for r in bq(
        truth_sql(
            EXTRACT_TABLE,
            [],
            [name],
            dims,
            hard,
            window,
            checks["students_sql"],
            checks["truth_filters"],
        )
    ):
        value, n = norm_key(r["g0"]), r["n_students"]
        if n and not seen.get(value):
            raise ScopeError(
                f"Cube returned no {checks['scope_measure']} for {name}={value}, but the "
                f"warehouse has {n} students. The Cube identity's scope is narrower than "
                "the dashboard's; rerun as a network-scoped user."
            )


def run_dashboard(
    checks,
    cube_load,
    bq,
    today,
    rows=None,
    scope_only=False,
    snapshots=None,
    audit=None,
) -> dict:
    window = resolve_window(checks, today)
    dims, hard = checks["dimensions"], checks["hard_filters"]
    scope_guard(checks, cube_load, bq, window)
    result = {
        "dashboard": checks["dashboard"],
        "window": _window_label(window),
        "run_date": today.isoformat(),
        "snapshots": snapshots or {},
        "rows": {},
    }
    if scope_only:
        return result
    selected = [r for r in checks["rows"] if rows is None or str(r["row_gid"]) in rows]

    # One Cube query and one SQL query per (view, table, grain), carrying every metric.
    jobs: dict[tuple, list[dict]] = {}
    for row in selected:
        where = (row.get("view", checks["view"]), EXTRACT_TABLE)
        for g in row["grains"]:
            metrics = jobs.setdefault((*where, tuple(g)), [])
            for m in row["metrics"]:
                if m["cube"] not in [x["cube"] for x in metrics]:
                    metrics.append(m)

    outcomes = {}
    for step_no, ((view, table, g), metrics) in enumerate(jobs.items(), 1):
        grain = [dims[n] for n in g]
        step = f"[{step_no}/{len(jobs)}] {view} {_label(g)}"
        if any(d.cube is None for d in grain):
            print(f"{step}: not comparable", file=sys.stderr, flush=True)
            outcomes[(view, table, g)] = {"status": "not_comparable"}
            continue
        print(step, file=sys.stderr, flush=True)

        def compare_job(ms, view=view, g=g, grain=grain):
            crows, preaggs = cube_load(
                cube_query(
                    view,
                    [m["cube"] for m in ms],
                    list(g),
                    dims,
                    hard,
                    window,
                    checks["cube_filters"],
                )
            )
            trows = bq(
                truth_sql(
                    EXTRACT_TABLE,
                    ms,
                    list(g),
                    dims,
                    hard,
                    window,
                    checks["students_sql"],
                    checks["truth_filters"],
                )
            )
            if not trows or (not g and not trows[0].get("n_students")):
                # Nothing to compare is never a pass (an empty window or extract).
                raise ValueError("the extract has no rows for this grain in the window")
            summaries = {}
            for i, m in enumerate(ms):
                cells = compare(
                    m["kind"],
                    cube_cells(crows, view, grain, m["cube"]),
                    truth_cells(trows, len(g), i, m["kind"]),
                )
                alt = None
                if m.get("missing_members"):
                    alt = truth_cells(trows, len(g), i, m["kind"], "_alt")
                    explain(cells, m["kind"], alt)
                summaries[m["cube"]] = summarize(cells, m["kind"], alt)
            return preaggs, summaries

        summaries, errors, preaggs = {}, {}, set()
        try:
            p_aggs, summaries = compare_job(metrics)
            preaggs |= set(p_aggs)
        except Exception as e:  # noqa: BLE001 - retried per metric below
            # One bad metric must not blank every row on this grain: retry each alone.
            for m in metrics if len(metrics) > 1 else []:
                try:
                    p_aggs, one = compare_job([m])
                    summaries.update(one)
                    preaggs |= set(p_aggs)
                except Exception as e1:  # noqa: BLE001 - recorded on the metric's rows
                    errors[m["cube"]] = f"{type(e1).__name__}: {e1}"[:300]
            if len(metrics) == 1:
                errors[metrics[0]["cube"]] = f"{type(e).__name__}: {e}"[:300]
        outcomes[(view, table, g)] = {
            "status": "ok",
            "pre_aggregations": sorted(preaggs),
            "metrics": summaries,
            "errors": errors,
        }

    for row in selected:
        where = (row.get("view", checks["view"]), EXTRACT_TABLE)
        grains = []
        missing: dict[str, dict] = {}
        for g in row["grains"]:
            o = outcomes[(*where, tuple(g))]
            entry = {"grain": list(g), "status": o["status"]}
            if o["status"] == "error":
                entry["error"] = o["error"]
            if o["status"] == "not_comparable":
                for name in g:
                    if dims[name].cube is None and not dims[name].tableau_only:
                        _missing(missing, name)["blocks_grains"].append(_label(g))
            errs = [
                o["errors"][m["cube"]]
                for m in row["metrics"]
                if m["cube"] in o.get("errors", {})
            ]
            if errs:
                entry.update(status="error", error=errs[0])
            elif o["status"] == "ok":
                ms = {m["cube"]: o["metrics"][m["cube"]] for m in row["metrics"]}
                bad = sum(s["bad"] for s in ms.values())
                explained = sum(s["explained"] for s in ms.values())
                for m in row["metrics"]:
                    only = ms[m["cube"]].get("only") or {}
                    w, t = only.get("without"), only.get("truth")
                    shown = SHOWN[m["kind"]]
                    # At the total, a member whose logic moves the dashboard's number
                    # causes part of the gap even when no cell is explained by it alone.
                    moves = (
                        not g
                        and w is not None
                        and t is not None
                        and abs(w - t) >= shown
                    )
                    for name in m.get("missing_members", []):
                        mm = _missing(missing, name)
                        mm["explains_cells"] += ms[m["cube"]]["explained"]
                        mm["changes_total"] = mm["changes_total"] or moves
                entry.update(
                    status="fail"
                    if bad
                    else ("missing_member" if explained else "pass"),
                    cells=sum(s["cells"] for s in ms.values()),
                    bad=bad,
                    explained=explained,
                    metrics=ms,
                    pre_aggregations=o["pre_aggregations"],
                )
            grains.append(entry)
        diagnosis = {}
        failing = {
            m
            for g in grains
            if g["status"] == "fail"
            for m, s in g["metrics"].items()
            if s["bad"]
        }
        for m in row["metrics"]:
            if m.get("diagnose_by") and m["cube"] in failing:
                diagnosis[m["cube"]] = _diagnose(
                    checks, cube_load, bq, window, where[0], m
                )
        a = (audit or {}).get(str(row["row_gid"]), {})
        verdict = row_verdict(grains)
        if (a.get("unaccounted") or a.get("error")) and verdict in (
            "pass",
            "missing_member",
        ):
            # A construct nobody accounted for may change what the sheet shows.
            verdict = "incomplete"
        result["rows"][str(row["row_gid"])] = {
            "name": row["name"],
            "verdict": verdict,
            "grains": grains,
            **({"diagnosis": diagnosis} if diagnosis else {}),
            "missing_members": {
                k: v
                for k, v in missing.items()
                if v["explains_cells"] or v["blocks_grains"] or v["changes_total"]
            },
            **({"unaccounted": a["unaccounted"]} if a.get("unaccounted") else {}),
            **({"not_checked": a["not_checked"]} if a.get("not_checked") else {}),
            **({"audit_error": a["error"]} if a.get("error") else {}),
        }
    return result


# ---------------------------------------------------------------- outputs
def _fmt(v, kind) -> str:
    if v is None:
        return "none"
    if kind == "rate":
        return f"{v * 100:.1f}%"
    return f"{v:,.1f}" if kind == "average" else f"{v:,.0f}"


def _window_text(window) -> str:
    start, end = window
    return start if start == end else f"{start} to {end}"


def _label(grain) -> str:
    return " x ".join(grain) or "total"


def _total_line(s_: dict, kind: str, members: list[str]) -> list[str]:
    """The total grain's line, and how much of it the missing members account for."""
    only = s_.get("only") or {}
    c, t = _fmt(only.get("cube"), kind), _fmt(only.get("truth"), kind)
    if s_["bad"]:
        lines = [f"- Total differs: Cube {c}, Tableau {t}."]
    elif s_["explained"]:
        lines = [
            f"- Total differs, explained by {', '.join(members)}: Cube {c}, Tableau {t}."
        ]
    else:
        lines = [f"- Total matches: Cube {c}, Tableau {t}."]
    w, truth = only.get("without"), only.get("truth")
    # A share that rounds to nothing at display precision is noise, not a cause.
    shown = SHOWN[kind]
    if members and w is not None and truth is not None and abs(w - truth) >= shown:
        gap = (
            f"{abs(w - truth) * 100:.1f} points"
            if kind == "rate"
            else _fmt(abs(w - truth), kind)
        )
        lines.append(
            f"- {', '.join(members)} accounts for {gap} (Tableau {t} with it, "
            f"{_fmt(w, kind)} without it)."
        )
    return lines


_COMPARED = ("pass", "fail", "missing_member")


def _missing_text(missing: dict, full: bool = False) -> str:
    parts = []
    for name, m in missing.items():
        bits = []
        if m["explains_cells"]:
            bits.append(f"explains {m['explains_cells']} cells")
        n = len(m["blocks_grains"])
        if n and full:
            bits.append(f"blocks {', '.join(m['blocks_grains'])}")
        elif n:
            bits.append(f"blocks {n} grain{'' if n == 1 else 's'}")
        parts.append(f"{name} ({'; '.join(bits)})")
    return ", ".join(parts)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def comment_text(row, result) -> str:
    """Three lines for Asana: verdict, members to add, what is left to investigate."""
    grains = row["grains"]
    compared = [g for g in grains if g["status"] in _COMPARED]
    bad = sum(g["bad"] for g in compared)
    first = f"Cube vs Tableau check, {result['run_date']}: {row['verdict'].replace('_', ' ').upper()}"
    if snaps := result.get("snapshots"):
        first += f" (extract {snaps['extract']}, Cube {snaps['cube']})"
    lines = [first]
    add = [
        f"{name} ({m['explains_cells']} cells)"
        if m["explains_cells"]
        else f"{name} (changes the total)"
        for name, m in row.get("missing_members", {}).items()
        if m["explains_cells"] or m.get("changes_total")
    ]
    if add:
        lines.append(f"Add to Cube: {', '.join(add)}.")
    if bad:
        n = sum(1 for g in compared if g["bad"])
        lines.append(
            f"Investigate: {bad} cells across {_plural(n, 'grain')}; details in the "
            f"{result['dashboard']} fix digest."
        )
    elif row["verdict"] == "missing_member":
        lines.append("Nothing else to investigate.")
    elif row["verdict"] == "pass":
        lines.append("Every compared cell matches.")
    errors = [g for g in grains if g["status"] == "error"]
    if errors:
        lines.append(
            f"Could not compare {_plural(len(errors), 'grain')}: {errors[0]['error']}"
        )
    return "\n".join(lines)


def _cell_text(c: dict, kind: str) -> str:
    if c["n_students"] is None or c["n_students"] < SMALL_CELL:
        return "small cell"
    return f"Cube {_fmt(c['cube'], kind)}, Tableau {_fmt(c['truth'], kind)}"


def _metric_sql(m: dict, without: bool = False) -> str:
    suffix = "_without" if without else ""
    if m["kind"] == "count":
        return f"`{m['sql' + suffix]}`"
    return f"`{m['num' + suffix]}` / `{m['den' + suffix]}`"


def _cube_text(name: str, d: dict | None) -> str:
    if not d:
        return f"{name}: definition not found under src/cube/model"
    where = " and ".join(f"`{f}`" for f in d["filters"])
    return f"{name} = {d['type']} of `{d['sql']}`" + (
        f" where {where}" if where else ""
    )


def digest_markdown(result, checks, cube_defs) -> str:
    """The fix list: members to add to Cube, then gaps nothing explains."""
    checks = checks or {"rows": [], "dimensions": {}}
    defs = {str(r["row_gid"]): r for r in checks["rows"]}
    members_doc = checks.get("members") or {}
    rows = result["rows"]
    verdicts = {}
    for row in rows.values():
        verdicts[row["verdict"]] = verdicts.get(row["verdict"], 0) + 1
    out = [f"# {result['dashboard']}: Cube fix digest, {result['run_date']}", ""]
    if snaps := result.get("snapshots"):
        out.append(f"Snapshots: extract {snaps['extract']}, Cube {snaps['cube']}.")
    out += [
        f"Window: {_window_text(result['window'])}. Rows: "
        + ", ".join(f"{n} {v.replace('_', ' ')}" for v, n in sorted(verdicts.items()))
        + ".",
        "",
        "## Add to Cube",
        "",
    ]
    adds: dict[str, dict] = {}
    blocked: dict[str, dict] = {}
    for gid, row in rows.items():
        for name, m in row.get("missing_members", {}).items():
            if m["explains_cells"] or m.get("changes_total"):
                a = adds.setdefault(name, {"cells": 0, "rows": []})
                a["cells"] += m["explains_cells"]
                a["rows"].append(gid)
            if m["blocks_grains"]:
                b = blocked.setdefault(name, {"grains": 0, "rows": 0})
                b["grains"] += len(m["blocks_grains"])
                b["rows"] += 1
    if not adds:
        out += ["No missing member explains a gap.", ""]
    for name, a in sorted(adds.items(), key=lambda kv: -kv[1]["cells"]):
        names = ", ".join(rows[g]["name"] for g in a["rows"])
        effect = f"explains {a['cells']} cells" if a["cells"] else "changes the total"
        out.append(
            f"### {name}: {effect} in {_plural(len(a['rows']), 'row')} ({names})"
        )
        doc = members_doc.get(name, {})
        for key, label in (
            ("what", "What"),
            ("lives_in", "Lives in"),
            ("suggested_edit", "Suggested edit"),
        ):
            if doc.get(key):
                out.append(f"- {label}: {doc[key]}")
        for g in a["rows"]:
            for m in defs.get(g, {}).get("metrics", []):
                if name in m.get("missing_members", []):
                    out.append(
                        f"- Dashboard logic: {_metric_sql(m, without=True)} without it, "
                        f"{_metric_sql(m)} with it"
                    )
                    break
            else:
                continue
            break
        out.append("")
    if blocked:
        out += ["### Dimensions the dashboard slices by that Cube lacks", ""]
        for name, b in sorted(blocked.items(), key=lambda kv: -kv[1]["grains"]):
            dim = checks["dimensions"].get(name)
            col = f"; dashboard field `{dim.sql}`" if dim else ""
            out.append(
                f"- {name}: blocks {_plural(b['grains'], 'grain')} in {_plural(b['rows'], 'row')}{col}"
            )
        out.append("")
    out += ["## Investigate", ""]
    any_gap = False
    for gid, row in rows.items():
        compared = [g for g in row["grains"] if g["status"] in _COMPARED]
        bad = sum(g["bad"] for g in compared)
        if not bad:
            continue
        any_gap = True
        cells = sum(g["cells"] for g in compared)
        out.append(
            f"### {row['name']} ({gid}): {bad} of {cells} cells out of tolerance"
        )
        for m, s_ in next(
            (g["metrics"] for g in compared if g["grain"] == []), {}
        ).items():
            mdef = next(
                (x for x in defs.get(gid, {}).get("metrics", []) if x["cube"] == m),
                {},
            )
            out += _total_line(
                s_, mdef.get("kind", "count"), mdef.get("missing_members", [])
            )
        worst_grain = max((g for g in compared if g["bad"]), key=lambda g: g["bad"])
        for s_ in worst_grain["metrics"].values():
            if s_["bad"]:
                c = s_["worst"][0]
                out.append(
                    f"- Worst grain: {_label(worst_grain['grain'])}, {_plural(s_['bad'], 'cell')}; "
                    f"{' / '.join(c['key']) or 'all'}: {_cell_text(c, c['kind'])}."
                )
                break
        for m, d in row.get("diagnosis", {}).items():
            kind = next(
                (
                    x["kind"]
                    for x in defs.get(gid, {}).get("metrics", [])
                    if x["cube"] == m
                ),
                "count",
            )
            label = d["by"] + (f" ({d['basis']})" if d.get("basis") else "")
            if d.get("error"):
                out.append(f"- By {label}: could not break down ({d['error']}).")
            elif d["cells"]:
                parts = "; ".join(
                    f"{c['value']} {_cell_text(c, kind)}" for c in d["cells"]
                )
                out.append(f"- By {label}: {parts}.")
            else:
                out.append(f"- By {label}: no value differs at the total.")
        for m in defs.get(gid, {}).get("metrics", []):
            out.append(f"- Dashboard: {m['cube']} = {_metric_sql(m)}")
            cdef = (cube_defs or {}).get(m["cube"])
            out.append(f"- Cube: {_cube_text(m['cube'], cdef)}")
            for r in (cdef or {}).get("refs", []):
                out.append(f"  - uses {_cube_text(r['name'], r)}")
        out.append("")
    if not any_gap:
        out += ["Nothing unexplained.", ""]
    return "\n".join(out)


def report_markdown(result) -> str:
    out = [
        f"# Cube vs Tableau: {result['dashboard']}",
        "",
        f"Run {result['run_date']}, window {_window_text(result['window'])}.",
        "",
        "Snapshots: extract {extract}, Cube {cube}.".format(
            **(result.get("snapshots") or {"extract": "n/a", "cube": "n/a"})
        ),
        "",
    ]
    for gid, row in result["rows"].items():
        out += [f"## {row['name']} ({gid}): {row['verdict']}", ""]
        if row.get("missing_members"):
            out += [
                f"Missing Cube members: {_missing_text(row['missing_members'], full=True)}.",
                "",
            ]
        for g in row["grains"]:
            line = f"- {_label(g['grain'])}: {g['status']}"
            if g["status"] in _COMPARED:
                line += f", {g['bad']} of {g['cells']} cells out of tolerance"
                if g.get("explained"):
                    line += f", {g['explained']} explained by missing members"
                if g["pre_aggregations"]:
                    line += f" (pre-aggregations: {', '.join(g['pre_aggregations'])})"
            if g["status"] == "error":
                line += f": {g['error']}"
            out.append(line)
            for metric, s in g.get("metrics", {}).items():
                for c in s["worst"]:
                    n = c["n_students"] if c["n_students"] is not None else "n/a"
                    out.append(
                        f"  - {metric} {' / '.join(c['key']) or 'all'}: "
                        f"Cube {_fmt(c['cube'], c['kind'])}, Tableau {_fmt(c['truth'], c['kind'])}, "
                        f"students {n}"
                    )
        out.append("")
    return "\n".join(out)


def write_outputs(result, out_dir: Path, checks=None, cube_defs=None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{result['run_date']}-{result['dashboard']}"
    report = out_dir / f"{stem}.md"
    for row in result["rows"].values():
        row["comment"] = comment_text(row, result)
    (out_dir / f"{stem}-fixes.md").write_text(
        digest_markdown(result, checks, cube_defs)
    )
    report.write_text(report_markdown(result))
    (out_dir / f"{stem}.json").write_text(json.dumps(result, indent=2, default=str))
    latest_path = out_dir / "latest.json"
    latest = (
        json.loads(latest_path.read_text()) if latest_path.exists() else {"rows": {}}
    )
    for gid, row in result["rows"].items():
        latest["rows"][gid] = {
            "verdict": row["verdict"],
            "date": result["run_date"],
            "dashboard": result["dashboard"],
            "name": row["name"],
            "missing_members": sorted(row.get("missing_members", {})),
            "reopen_for": reopen_for(row),
        }
    latest_path.write_text(json.dumps(latest, indent=2))
    return report


def _user_email(given: str | None) -> str:
    email = (given or os.environ.get("CUBE_USER_EMAIL", "")).strip()
    if not email and USER_EMAIL_CACHE.exists():
        email = USER_EMAIL_CACHE.read_text().strip()
    if not email:
        sys.exit("No Cube identity: pass --as <email> or set CUBE_USER_EMAIL.")
    return email


def _run_command(a) -> int:
    secret = os.environ.get("CUBE_API_SECRET", "")
    if not secret:
        sys.exit(
            "CUBE_API_SECRET is not set: run this inside a throwaway pytest "
            "(see .claude/skills/cube-dashboard/SKILL.md)."
        )
    checks = load_checks(a.checks)
    cube = CubeClient(a.cube_url, secret, _user_email(a.email))
    print("downloading the workbook extract", file=sys.stderr, flush=True)
    hyper, extract_at = download_extract(
        checks["extract"]["workbook_luid"],
        checks["extract"]["datasource"],
        SCRATCH / checks["dashboard"],
    )
    cube_at = cube_built_at(checks["cube_source_table"], bigquery_rows)
    audit = audit_rows(checks, SCRATCH / checks["dashboard"] / "workbook.twb")
    try:
        timing_guard(extract_at, cube_at)
        with ExtractSource(hyper) as truth:
            result = run_dashboard(
                checks,
                cube.load,
                truth,
                snapshot_date(extract_at),
                rows=set(a.rows.split(",")) if a.rows else None,
                scope_only=a.scope_only,
                snapshots={"extract": _local(extract_at), "cube": _local(cube_at)},
                audit=audit,
            )
    except (TimingError, ScopeError) as e:
        sys.exit(str(e))
    if a.scope_only:
        print("scope ok")
        return 0
    cube_defs = {
        m["cube"]: cube_definition(m["cube"], r.get("view", checks["view"]))
        for r in checks["rows"]
        for m in r["metrics"]
    }
    report = write_outputs(result, a.out, checks, cube_defs)
    print(f"digest: {a.out / (report.stem + '-fixes.md')}")
    for gid, row in result["rows"].items():
        print(f"{row['verdict']:<10} {gid} {row['name']}")
    print(f"report: {report}")
    return 0 if all(r["verdict"] == "pass" for r in result["rows"].values()) else 1


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
    r = sub.add_parser("run", help="compare Cube with the warehouse for a checks file")
    r.add_argument("checks")
    r.add_argument("--rows", help="comma-separated Asana row gids (default: all)")
    r.add_argument("--scope-only", action="store_true", help="run only the scope guard")
    r.add_argument(
        "--as", dest="email", help="Cube identity (default: CUBE_USER_EMAIL)"
    )
    r.add_argument("--cube-url", default=DEFAULT_CUBE_URL)
    r.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = p.parse_args(argv)
    return _grains_command(a) if a.cmd == "grains" else _run_command(a)


if __name__ == "__main__":
    sys.exit(main())
