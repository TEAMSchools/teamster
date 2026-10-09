"""Compare Cube with what a Tableau dashboard shows, at every grain its sheets use.

    uv run scripts/cube_validate.py grains <workbook.twb> --dashboard "<name>" [...] [--measure "<caption>"]
    uv run scripts/cube_validate.py run <checks.yml> [--rows <gid,...>] [--scope-only]
    uv run scripts/cube_validate.py settle <checks.yml>

`grains` reads a downloaded .twb and proposes the grains for one measure's check entry.
`run` needs CUBE_API_SECRET, which only the pytest secrets fixture provides, so it runs
inside a throwaway tests/test_zz_*.py. `settle` compares each extract with its live
warehouse table by date and recommends `settle.days`. Runbook: .claude/skills/cube-dashboard/SKILL.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import threading
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
# "Total using" on a measure: usr:<field>:vtavg:qk
_VISUAL_TOTAL = re.compile(r":vt([a-z]+)(?=:[a-z]+(?::\d+)?$)")


def _strip_visual_total(inner: str) -> tuple[str, str | None]:
    """A shelf token without its visual-total segment, and that setting."""
    m = _VISUAL_TOTAL.search(inner)
    if not m:
        return inner, None
    return inner[: m.start()] + inner[m.end() :], m.group(1)


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
    # The measures it changes; empty means every measure on the sheet.
    scope: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.kind}: {self.name}"

    @property
    def ref(self) -> str:
        """The key plus a fingerprint of what the construct does: editing a filter's
        members or a group's bins changes the ref, so a stale checks entry shows."""
        if not self.detail:
            return self.key
        canon = json.dumps(_canon(self.detail), default=str).encode()
        return f"{self.key} [{hashlib.sha256(canon).hexdigest()[:6]}]"


def _canon(v):
    """A detail value in a fixed order, whatever its key types."""
    if isinstance(v, dict):
        return sorted(([str(k), _canon(x)] for k, x in v.items()), key=lambda p: p[0])
    if isinstance(v, list | tuple):
        return [_canon(x) for x in v]
    return v


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
        # A calculation typed on a sheet lives only in its datasource-dependencies.
        for dep in root.iter("datasource-dependencies"):
            for col in dep.findall("column"):
                if col.find("calculation") is not None:
                    self.cols.setdefault(
                        (_attr(dep, "datasource"), _attr(col, "name")), col
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
    """Every construct that can change what this sheet shows.

    A construct reached only through one measure (its shelf token or its formula) is
    scoped to that measure; the rest change every measure on the sheet.
    """
    found: dict[str, Construct] = {}

    def add(c: Construct | None, scope: list[str] | tuple[str, ...] = ()) -> None:
        if c is None:
            return
        c.scope = list(scope)
        have = found.get(c.ref)
        if have is None:
            found[c.ref] = c
        elif have.scope and c.scope:
            have.scope = list(dict.fromkeys(have.scope + c.scope))
        else:
            have.scope = []

    tokens = _sheet_tokens(w)
    filtered = set(
        _TOKEN.findall(
            " ".join(
                _attr(f, "column")
                for f in w.iter("filter")
                if not _attr(f, "column").endswith("[:Measure Names]")
            )
        )
    )
    instances = {_attr(ci, "name"): ci for ci in w.iter("column-instance")}
    reach: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    for ds, token in tokens:
        add(_set_construct(book, ds, token))
        inner, visual_total = _strip_visual_total(token)
        m = _INSTANCE.match(inner)
        if not m:
            continue
        deriv, fld, _ = m.groups()
        add(_set_construct(book, ds, fld))
        kind, label, _ = _classify(ds, inner, columns)
        # A filter changes every measure; a measure's own token changes only it.
        scope = (label,) if kind == "measure" and (ds, token) not in filtered else ()
        wrapped = _NESTED.match(fld)
        if wrapped and wrapped.group(1) in _MEASURE_DERIVATIONS:
            fld = wrapped.group(2)
            ci = instances.get(f"[{token}]")
            tc = ci.find("table-calc") if ci is not None else None
            quick = _attr(tc, "type") if tc is not None else deriv
            add(Construct("table_calc", label, detail={"quick": quick or deriv}), scope)
        if visual_total and visual_total not in ("none", "auto", "automatic"):
            add(
                Construct("total", label, detail={"visual_totals": visual_total}), scope
            )
        reach.setdefault((ds, scope), []).append(f"[{fld}]")
        start = _fiscal_start(book, ds, f"[{fld}]")
        if deriv in ("yr", "tyr", "qr", "tqr") and start:
            add(Construct("fiscal_year", label, detail={"start_month": start}), scope)
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
        add(Construct("alias", alias, detail={"field": caption}), (caption, alias))
    for (ds, scope), names in reach.items():
        for n in book.closure(ds, names):
            for c in _field_constructs(book, ds, n):
                add(c, scope)
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
    out: dict[tuple[str, str], tuple[str, str]] = {}

    def put(ds: str, col: ET.Element) -> None:
        calc = col.find("calculation")
        out.setdefault(
            (ds, _attr(col, "name")),
            (
                _attr(col, "caption") or _attr(col, "name").strip("[]"),
                _attr(calc, "formula")
                if calc is not None and calc.get("class", "tableau") == "tableau"
                else "",
            ),
        )

    for ds in root.findall("datasources/datasource"):
        for col in ds.findall("column"):
            put(_attr(ds, "name"), col)
    # A calculation typed on a sheet lives only in its datasource-dependencies.
    for dep in root.iter("datasource-dependencies"):
        for col in dep.findall("column"):
            if col.find("calculation") is not None:
                put(_attr(dep, "datasource"), col)
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
    inner = _strip_visual_total(inner)[0]
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
        # (datasource, '[field]') on the shelves: a hierarchy belongs to one field.
        on_shelf: set[tuple[str, str]] = set()

        def take(text: str, dims: list[str], s=s, raw=raw, on_shelf=on_shelf) -> None:
            for ds, inner in _TOKEN.findall(text):
                if m := _INSTANCE.match(_strip_visual_total(inner)[0]):
                    on_shelf.add((ds, f"[{m.group(2)}]"))
                s.datasource = s.datasource or str(ds_caption.get(ds) or ds)
                if ds not in raw:
                    raw.append(ds)
                kind, label, formula = _classify(ds, inner, columns)
                branches = _param_branches(columns, ds, formula)
                if kind == "dim" and label not in dims:
                    dims.append(label)
                    if branches:
                        # The value the sheet opens at: the parameter's current value.
                        param = book.cols.get(
                            ("Parameters", f"[{branches['parameter']}]")
                        )
                        branches["default"] = (
                            _tableau_value(_attr(param, "value"))
                            if param is not None
                            else None
                        )
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
            for fields in book.drill_paths.get(ds, []):
                labels = [_resolve(columns, ds, n.strip("[]"))[0] for n in fields]
                if any((ds, n) in on_shelf for n in fields):
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


def _substitute(s: Sheet, shelves: list[list[str]]) -> list[list[str]]:
    """Each shelf once per parameter value, its parameter fields replaced by the branch."""
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
    return shelves


def _shelves(s: Sheet) -> list[list[str]]:
    """The sheet's shelf grain once per drill level and per parameter value."""
    shelves = [list(s.shelf_dims)]
    # Drill levels expand on the shelf as stored, before any parameter is substituted.
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
    shelves = _substitute(s, shelves)
    return [list(t) for t in dict.fromkeys(tuple(sh) for sh in shelves)]


def _subtotal_grains(s: Sheet) -> list[list[str]]:
    """A subtotal on d totals the fields nested inside d on its axis."""
    raw = []
    for d in s.subtotal_dims:
        axis = s.rows_dims if d in s.rows_dims else s.cols_dims
        if d in axis:
            inner = axis[axis.index(d) + 1 :]
            raw.append([x for x in s.shelf_dims if x not in inner])
    return _substitute(s, raw)


def _base_shelf(s: Sheet) -> list[str]:
    """The grain the sheet opens at: each parameter at its value, drill levels as stored."""
    out = []
    for d in s.shelf_dims:
        p = s.param_dims.get(d)
        if p is None:
            out.append(d)
            continue
        value = p.get("default")
        if value not in p["branches"]:
            value = next(iter(p["branches"]))
        out.append(p["branches"][value])
    return _dedupe(out)


def propose_grains(sheets: list[Sheet], measure: str) -> list[list[str]]:
    """The total; each sheet's shelf grains and subtotals; each filter added to the
    grain the sheet opens at, one at a time."""
    grains: list[list[str]] = [[]]
    seen = {()}

    def add(g: list[str]) -> None:
        # The same fields in another order are the same cut.
        if tuple(sorted(g)) not in seen:
            seen.add(tuple(sorted(g)))
            grains.append(list(g))

    for s in sheets:
        if measure not in s.measures and measure not in s.measure_aliases:
            continue
        for g in _shelves(s) + _subtotal_grains(s):
            add(g)
        base = _base_shelf(s)
        add(base)
        for f in s.filter_dims:
            if f not in base:
                add(base + [f])
    return grains


def merge_constructs(sheets: list[Sheet]) -> list[Construct]:
    """Each construct once, with every sheet it appears on."""
    out: dict[str, Construct] = {}
    for s in sheets:
        for c in s.constructs:
            m = out.get(c.ref)
            if m is None:
                m = out[c.ref] = Construct(c.kind, c.name, [], c.detail, list(c.scope))
            elif m.scope and c.scope:
                m.scope = list(dict.fromkeys(m.scope + c.scope))
            else:
                m.scope = []
            if s.name not in m.sheets:
                m.sheets.append(s.name)
    return list(out.values())


def _public(c: Construct) -> dict:
    """A construct for output. Filter and set members, and group bin values, become
    counts: they can be student names or ids, and outputs carry aggregates only."""
    out = dict(asdict(c), key=c.key, ref=c.ref)
    d = dict(out["detail"])
    if isinstance(d.get("members"), list):
        d["members"] = len(d["members"])
    if isinstance(d.get("bins"), dict):
        d["bins"] = {str(k): len(v) for k, v in d["bins"].items()}
    out["detail"] = d
    return out


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
        # A construct scoped to another measure on the same sheet is not this row's.
        found = [
            c
            for c in merge_constructs(using)
            if not c.scope or any(x in captions for x in c.scope)
        ]
        out[gid] = {
            "not_checked": [
                dict(_public(c), why=why[c.ref]) for c in found if c.ref in why
            ],
            "unaccounted": [
                _public(c)
                for c in found
                if c.ref not in why and c.ref not in checks["handled"]
            ],
        }
    return out


def workbook_exclusions(checks: dict, twb) -> list[dict]:
    """Extract-side conditions dropping the members of the named workbook filters.

    The members (test records) are read from the workbook on every run and go only
    into the SQL, never into a file or an output.
    """
    if not checks["workbook_excludes"]:
        return []
    found = merge_constructs(parse_twb(twb, checks["dashboards"]))
    out = []
    for x in checks["workbook_excludes"]:
        members = [
            v
            for c in found
            if c.key == x["construct"]
            for v in c.detail.get("members", [])
            if v is not None
        ]
        if x.get("pattern"):
            pat = re.compile(x["pattern"])
            members = [
                _tableau_value(m.group(1)) for v in members if (m := pat.search(str(v)))
            ]
        if not members:
            # A silent no-op would let the test records back into the comparison.
            raise CheckError(
                f"the workbook gives no members for {x['construct']}: the filter is "
                "gone, empty, or its pattern matches nothing"
            )
        values = ", ".join(_sql_literal(v) for v in dict.fromkeys(members))
        # private: the members are test-record ids, so no draft or output repeats them.
        out.append({"sql": f"{x['sql']} not in ({values})", "private": True})
    return out


# ---------------------------------------------------------------- checks files and queries
CUBE_LIMIT = 50_000
# An average is a rate on its own scale (a scale score): compared in its units.
KINDS = {"count", "rate", "average"}
# Where a truth issue lives, and the two answers a domain owner can give.
TRUTH_WHERE = ("dashboard", "rpt", "source")
RULINGS = ("cube-correct", "cube-wrong")


class CheckError(ValueError):
    """A checks file that cannot be run as written."""


@dataclass(frozen=True)
class Dim:
    name: str
    cube: str | None  # None: no Cube member, so grains using it are not comparable
    sql: str
    granularity: str | None = None
    tableau_only: bool = False  # a dashboard control, not data: never a missing member
    # A Tableau group: relabel (codes rolled into buckets) or rule (a definition).
    group_kind: str | None = None
    # Identifies a person: outputs show this in place of its values. True means a
    # student ("a student"); a string names someone else ("a teacher").
    person: bool | str = False
    # The same field under another column name in another extract: (datasource, sql).
    sql_by_datasource: tuple[tuple[str, str], ...] = ()

    def sql_for(self, datasource: str | None) -> str:
        return dict(self.sql_by_datasource).get(datasource or "", self.sql)


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
            d.get("person")
            if isinstance(d.get("person"), str)
            else bool(d.get("person")),
            tuple(sorted((d.get("sql_by_datasource") or {}).items())),
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
    # Gaps the dashboard, its rpt_ model or the source causes, for the domain owner.
    issues = data.get("truth_issues") or {}
    if not isinstance(issues, dict):
        raise CheckError(f"{path}: truth_issues is a map of slug to entry")
    for slug, t in issues.items():
        at = f"{path}: truth issue '{slug}'"
        missing = [k for k in ("title", "what", "where") if not (t or {}).get(k)]
        if missing:
            raise CheckError(f"{at} is missing {missing}")
        if t["where"] not in TRUTH_WHERE:
            raise CheckError(f"{at}: where must be one of {', '.join(TRUTH_WHERE)}")
        if t.get("issue") is not None and not isinstance(t["issue"], int):
            raise CheckError(f"{at}: issue is the GitHub issue number")
        r = t.get("ruling")
        if r is not None and not (
            isinstance(r, dict)
            and r.get("call") in RULINGS
            and r.get("by")
            and r.get("on")
        ):
            raise CheckError(
                f"{at}: ruling needs call (cube-correct or cube-wrong), by and on"
            )
        t["labels"] = list(t.get("labels") or [])
    data["truth_issues"] = issues
    data["open_issues_task"] = (
        str(data["open_issues_task"]) if data.get("open_issues_task") else None
    )
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
            without = "sql_without" if m["kind"] == "count" else "num_without"
            if m.get("missing_members") and not m.get("variants"):
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
            variants = list(m.get("variants") or [])
            if m.get("missing_members") and m.get(without):
                # The SQL without the missing members is the variant that explains them.
                keys = ("sql",) if m["kind"] == "count" else ("num", "den")
                variants.insert(
                    0,
                    {
                        "explains": list(m["missing_members"]),
                        **{k: m[f"{k}_without"] for k in keys},
                    },
                )
            need = (
                ("explains", "sql")
                if m["kind"] == "count"
                else ("explains", "num", "den")
            )
            for v in variants:
                if not isinstance(v, dict) or any(not v.get(k) for k in need):
                    raise CheckError(
                        f"{where}: metric {m.get('cube')}: each variant needs "
                        f"{list(need)}"
                    )
                known = set(issues) | set(m.get("missing_members") or [])
                unknown = [n for n in v["explains"] if n not in known]
                if unknown:
                    raise CheckError(
                        f"{where}: metric {m.get('cube')}: a variant explains unknown "
                        f"{unknown}; name a missing member or a truth issue"
                    )
            m["variants"] = variants
        for m in row["metrics"]:
            t = m.get("tableau")
            m["tableau"] = [t] if isinstance(t, str) else list(t or [])
            # A metric reads the checks file's extract unless it names another one.
            default = data["extract"]["datasource"]
            m["datasource"] = m.get("datasource") or default
            m["key"] = (
                m["cube"]
                if m["datasource"] == default
                else f"{m['cube']} @ {m['datasource']}"
            )
        keys = [m["key"] for m in row["metrics"]]
        if len(keys) != len(set(keys)):
            raise CheckError(
                f"{where}: a metric is listed twice on one extract; give the second a "
                "different datasource or drop it"
            )
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
    # Workbook filters whose members (test records) the extract side also drops. The
    # members are read from the workbook on each run, so no id or name sits in git.
    data["workbook_excludes"] = list(data.get("workbook_excludes") or [])
    for x in data["workbook_excludes"]:
        if not (_construct_key_ok(x.get("construct")) and x.get("sql")):
            raise CheckError(
                f"{path}: workbook_excludes entries need construct ('<kind>: <name>') "
                "and sql"
            )
    data["handled"] = dict(data.get("handled") or {})
    for key in data["handled"]:
        if not _construct_key_ok(key):
            raise CheckError(f"{path}: handled names unknown construct '{key}'")
    # One run query carries each metric once, so its SQL must agree across rows; the
    # Tableau captions and the breakdown field are per row and may differ.
    definition = (
        "kind",
        "sql",
        "num",
        "den",
        "missing_members",
        "sql_without",
        "num_without",
        "den_without",
        "variants",
    )
    seen: dict[str, dict] = {}
    for row in data["rows"]:
        for m in row["metrics"]:
            sql = {k: m.get(k) for k in definition}
            first = seen.setdefault(m["key"], sql)
            if first != sql:
                raise CheckError(
                    f"{path}: metric {m['cube']} is defined twice with different "
                    "SQL; rows that share a Cube member must share its definition"
                )
    data["dimensions"] = dims
    # Cube-side only: what the dashboard's table already excludes (e.g. break days).
    data.setdefault("cube_filters", [])
    # Extract-side only: rows the dashboard's table holds that Cube never carries.
    data.setdefault("truth_filters", [])
    settle = data.get("settle")
    if settle is not None and not (
        isinstance(settle, dict)
        and isinstance(settle.get("days"), int)
        and isinstance(settle.get("truth"), str)
        and isinstance(settle.get("cube"), list)
        and isinstance(settle.get("date", ""), str)
    ):
        raise CheckError(
            f"{path}: settle needs days (an integer), truth (SQL with {{cutoff}}), "
            "cube (filters with {cutoff}) and, for the settle command, date (SQL)"
        )
    # Several academic years are compared year by year, never pooled.
    if window and len(window["academic_years"]) > 1:
        for row in data["rows"]:
            row["grains"] = [
                list(t)
                for t in dict.fromkeys(
                    tuple(g if "academic_year" in g else [*g, "academic_year"])
                    for g in row["grains"]
                )
            ]
    data.setdefault("scope_measure", "count_students")
    data.setdefault("students_sql", "count(distinct student_number)")
    data["path"] = str(path)
    return data


def academic_window(today: dt.date) -> tuple[dt.date, dt.date]:
    """July 1 of the academic year that contains yesterday, through yesterday."""
    end = today - dt.timedelta(days=1)
    return dt.date(end.year if end.month >= 7 else end.year - 1, 7, 1), end


def _fill(value, cutoff: str):
    """A filter tree with {cutoff} replaced in every string."""
    if isinstance(value, str):
        return value.replace("{cutoff}", cutoff)
    if isinstance(value, list):
        return [_fill(v, cutoff) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, cutoff) for k, v in value.items()}
    return value


def settle_filters(checks: dict, extract_date: dt.date) -> tuple[str, list]:
    """Truth and Cube filters that leave out scores from the settle window: the days
    before the extract refreshed, where scores are still being entered and corrected."""
    settle = checks["settle"]
    cutoff = (extract_date - dt.timedelta(days=settle["days"])).isoformat()
    return _fill(settle["truth"], cutoff), _fill(settle["cube"], cutoff)


def settle_sql(checks: dict, datasource: str, table: str, window) -> str:
    """Every metric on one extract, by the settle date: what drift is measured on."""
    seen: dict[str, dict] = {}
    for r in checks["rows"]:
        for m in r["metrics"]:
            if m["datasource"] == datasource:
                # A variant is a correction, not data: it is not drift.
                seen.setdefault(m["key"], {**m, "variants": []})
    dims = {
        **checks["dimensions"],
        "_day": Dim("_day", None, checks["settle"]["date"]),
    }
    return truth_sql(
        table,
        list(seen.values()),
        ["_day"],
        dims,
        checks["hard_filters"],
        window,
        checks["students_sql"],
        checks["truth_filters"],
        datasource,
    )


def settle_drift(extract_rows, live_rows, refreshed: dt.date) -> dict:
    """Which days changed between the extract and the live table, by age."""

    def by_day(rows):
        return {
            norm_key(r["g0"]): {k: _num(v) or 0.0 for k, v in r.items() if k != "g0"}
            for r in rows
        }

    ext, live = by_day(extract_rows), by_day(live_rows)
    days, undated = [], None
    for day in sorted(set(ext) | set(live)):
        a, b = ext.get(day, {}), live.get(day, {})
        changes = {
            k: b.get(k, 0.0) - a.get(k, 0.0)
            for k in sorted(set(a) | set(b))
            if abs(b.get(k, 0.0) - a.get(k, 0.0)) > 1e-9
        }
        if not changes:
            continue
        if day == "∅":
            undated = changes
            continue
        age = (refreshed - dt.date.fromisoformat(day)).days
        days.append({"day": day, "age": age, "changes": changes})
    # A row dated after the refresh is past the cutoff of any window, so it never
    # sets the window's length.
    past = [x["age"] for x in days if x["age"] >= 0]
    oldest = max(past) if past else None
    return {
        "days": days,
        "undated": undated,
        "oldest_age": oldest,
        "recommend": max(1, (oldest if oldest is not None else 0) + 1),
    }


def settle_text(datasource: str, drift: dict, labels: dict) -> str:
    def changes(c: dict) -> str:
        return "; ".join(f"{labels.get(k, k)} {v:+,.0f}" for k, v in c.items())

    out = [f"{datasource}:", "  day         age  changes"]
    out += [
        f"  {x['day']}  {x['age']:>3}  {changes(x['changes'])}" for x in drift["days"]
    ]
    if drift["undated"]:
        out.append(
            f"  rows with no date (no cutoff settles them): {changes(drift['undated'])}"
        )
    oldest = drift["oldest_age"]
    out.append(
        "  oldest change: "
        + (f"{oldest} days before the refresh" if oldest is not None else "none")
        + f"; days: {drift['recommend']}"
    )
    return "\n".join(out)


def _settle_labels(checks: dict, datasource: str) -> dict:
    labels, seen = {"n_students": "students"}, []
    for r in checks["rows"]:
        for m in r["metrics"]:
            if m["datasource"] != datasource or m["key"] in seen:
                continue
            i = len(seen)
            seen.append(m["key"])
            if m["kind"] == "count":
                labels[f"m{i}"] = m["key"]
            else:
                labels[f"m{i}_num"] = f"{m['key']} numerator"
                labels[f"m{i}_den"] = f"{m['key']} denominator"
    return labels


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


def cube_filters_for(cube_filters, datasource: str | None) -> list[dict]:
    """Cube filters for queries beside one extract: a filter without `datasource`
    applies to every extract, one with it only to metrics read from that extract."""
    return [
        {k: v for k, v in f.items() if k != "datasource"}
        for f in cube_filters
        if f.get("datasource") in (None, datasource)
    ]


def _prefixed(view: str, f: dict) -> dict:
    """A Cube filter with its members named on the view, including inside or/and."""
    for op in ("or", "and"):
        if op in f:
            return {op: [_prefixed(view, x) for x in f[op]]}
    return dict(f, member=f"{view}.{f['member']}")


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
        + [_prefixed(view, f) for f in cube_filters],
        "limit": CUBE_LIMIT,
        "timezone": "UTC",
    }


def _sql_literal(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v)
    return "'" + str(v).replace("'", "\\'") + "'"


def _filters_for(truth_filters, datasource: str | None, public_only=False) -> list[str]:
    """Truth filters that apply to one extract: a plain string applies to every one.

    public_only drops the test-record filters, for SQL that leaves this machine.
    """
    out = []
    for f in truth_filters:
        if isinstance(f, str):
            out.append(f)
        elif f.get("datasource") in (None, datasource) and not (
            public_only and f.get("private")
        ):
            out.append(f["sql"])
    return out


def _truth_where(
    dims, hard_filters, window, truth_filters, datasource, public_only=False
) -> list[str]:
    if isinstance(window, dict):
        years = ", ".join(str(y) for y in window["academic_years"])
        where = [f"{dims['academic_year'].sql_for(datasource)} in ({years})"]
    else:
        where = [
            f"{dims['date'].sql_for(datasource)} between '{window[0]}' and '{window[1]}'"
        ]
    for f in hard_filters:
        values = ", ".join(_sql_literal(v) for v in f["values"])
        where.append(f"{dims[f['dim']].sql_for(datasource)} in ({values})")
    return where + _filters_for(truth_filters, datasource, public_only)


def truth_sql(
    table,
    metrics,
    grain,
    dims,
    hard_filters,
    window,
    students_sql,
    truth_filters=(),
    datasource=None,
) -> str:
    select = [f"{dims[n].sql_for(datasource)} as g{i}" for i, n in enumerate(grain)]
    for i, m in enumerate(metrics):
        if m["kind"] == "count":
            select.append(f"{m['sql']} as m{i}")
        else:
            select += [f"{m['num']} as m{i}_num", f"{m['den']} as m{i}_den"]
        for j, v in enumerate(m.get("variants", [])):
            if m["kind"] == "count":
                select.append(f"{v['sql']} as m{i}_v{j}")
            else:
                select += [
                    f"{v['num']} as m{i}_v{j}_num",
                    f"{v['den']} as m{i}_v{j}_den",
                ]
    select.append(f"{students_sql} as n_students")
    where = _truth_where(dims, hard_filters, window, truth_filters, datasource)
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
    # Fails as written, but matches a variant: the names that variant explains.
    explained_by: tuple[str, ...] = ()
    variant: float | None = None  # that variant's value

    @property
    def explained(self) -> bool:
        return bool(self.explained_by)

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


def explain(cells, kind, variants) -> None:
    """Mark failed cells that match a variant; the first that matches names the cause."""
    for c in cells:
        if c.ok:
            continue
        for names, alt in variants:
            v = alt.get(c.key, (None, None))[0]
            if _matches(kind, c.cube, v):
                c.explained_by, c.variant = tuple(names), v
                break


def _cell_out(c, kind) -> dict:
    return {
        "key": list(c.key),
        "cube": c.cube,
        "truth": c.truth,
        "n_students": c.n_students,
        "kind": kind,
    }


def without_index(m: dict) -> int | None:
    """The variant that is the SQL without the missing members, if the metric has one."""
    members = set(m.get("missing_members") or [])
    return next(
        (
            j
            for j, v in enumerate(m.get("variants", []))
            if members and set(v["explains"]) == members
        ),
        None,
    )


def summarize(
    cells, kind, without=None, accepted=frozenset(), open_issues=frozenset()
) -> dict:
    """One metric at one grain.

    A cell explained only by truth issues ruled cube-correct is accepted: the
    dashboard is wrong there and Cube is right, so it counts as a match.
    """

    def is_accepted(c):
        return c.explained and set(c.explained_by) <= accepted

    bad = sorted(
        (c for c in cells if not c.ok and not c.explained), key=lambda c: -c.delta
    )
    explained = [c for c in cells if c.explained and not is_accepted(c)]
    by: dict[str, int] = {}
    for c in cells:
        for n in c.explained_by:
            by[n] = by.get(n, 0) + 1
    only = None
    if len(cells) == 1:
        only = {"cube": cells[0].cube, "truth": cells[0].truth}
        if without is not None:
            only["without"] = without.get(cells[0].key, (None, None))[0]
    shown = sorted((c for c in cells if c.explained), key=lambda c: -c.delta)
    return {
        "cells": len(cells),
        "bad": len(bad),
        "explained": len(explained),
        "review": sum(1 for c in explained if set(c.explained_by) & open_issues),
        "accepted": sum(1 for c in cells if is_accepted(c)),
        "explained_by": by,
        "only": only,
        "worst": [_cell_out(c, kind) for c in bad[:5]],
        "examples": [
            dict(_cell_out(c, kind), variant=c.variant, explains=list(c.explained_by))
            for c in shown[:3]
        ],
    }


def row_verdict(grains) -> str:
    statuses = [g["status"] for g in grains]
    if "fail" in statuses:
        return "fail"
    if "error" in statuses:
        return "incomplete"
    for s in ("truth_issue", "missing_member"):
        if s in statuses:
            return s
    if "pass" not in statuses:
        return "incomplete"
    return "pass"


def issue_states(checks) -> tuple[frozenset, frozenset, frozenset]:
    """Truth issues the owner ruled cube-correct, ruled cube-wrong, and not yet ruled."""
    calls = {
        s: (t.get("ruling") or {}).get("call")
        for s, t in (checks.get("truth_issues") or {}).items()
    }
    return (
        frozenset(s for s, c in calls.items() if c == "cube-correct"),
        frozenset(s for s, c in calls.items() if c == "cube-wrong"),
        frozenset(s for s, c in calls.items() if c is None),
    )


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


def _httpx_client():
    import httpx

    return httpx.Client(timeout=60)


class CubeClient:
    def __init__(
        self, url, secret, email, http=None, sleep=time.sleep, http_factory=None
    ):
        self.url, self.secret, self.email = url.rstrip("/"), secret, email
        self._shared = http
        self._factory = http_factory or _httpx_client
        self._local = threading.local()
        self.sleep = sleep

    def _http(self):
        """One HTTP client per thread, so parallel runs never share a connection pool."""
        if self._shared is not None:
            return self._shared
        if getattr(self._local, "client", None) is None:
            self._local.client = self._factory()
        return self._local.client

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
        overloaded = 0
        for _ in range(120):
            r = self._http().post(
                f"{self.url}/load",
                json={"query": query},
                headers={"Authorization": self._token()},
            )
            if r.status_code in (429, 502, 503, 504) and overloaded < 5:
                # Cube Cloud is busy (other users, or this run's own workers): back off.
                overloaded += 1
                self.sleep(2**overloaded)
                continue
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


_CAPTION = re.compile(r"^(\w+) \((\w+)\)$")


def live_table(datasource: str) -> str:
    """The warehouse table behind a datasource captioned `rpt_x (dataset)`."""
    m = _CAPTION.match(datasource)
    if not m:
        raise CheckError(
            f"datasource '{datasource}' is not captioned 'rpt_x (dataset)', so its "
            "warehouse table is unknown"
        )
    return f"{BQ_PROJECT}.{m.group(2)}.{m.group(1)}"


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


def unpack_extracts(
    twbx: Path, datasources: list[str], out_dir: Path
) -> dict[str, tuple[Path, dt.datetime | None]]:
    """Each datasource's .hyper from a downloaded .twbx, with that extract's refresh time."""
    import zipfile

    out_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    with zipfile.ZipFile(twbx) as z:
        twb = next(n for n in z.namelist() if n.endswith(".twb"))
        (out_dir / "workbook.twb").write_bytes(z.read(twb))
        for ds in datasources:
            name = extract_file_name(out_dir / "workbook.twb", ds)
            member = next(n for n in z.namelist() if Path(n).name == name)
            hyper = out_dir / name
            hyper.write_bytes(z.read(member))
            out[ds] = (hyper, extract_refresh_time(out_dir / "workbook.twb", ds))
    return out


def download_extract(
    luid: str, datasources: list[str], out_dir: Path
) -> dict[str, tuple[Path, dt.datetime]]:
    """Download the workbook once; return each datasource's .hyper and refresh time."""
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

    workbook_at, twbx = retry(fetch)
    out = {}
    for ds, (hyper, at) in unpack_extracts(twbx, datasources, out_dir).items():
        # The datasource's own refresh time; the workbook's also moves on republish.
        at = at or workbook_at
        if at is None:
            raise TimingError(f"Tableau returned no refresh time for {ds} in {luid}")
        out[ds] = (hyper, at)
    return out


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


def window_is_closed(window, today: dt.date) -> bool:
    """True when every academic year in the window has ended: no new scores arrive,
    so the extract and Cube agree whenever each was built."""
    if not isinstance(window, dict):
        return False
    current = today.year if today.month >= 7 else today.year - 1
    return all(y < current for y in window["academic_years"])


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
    without = "sql_without" if metric["kind"] == "count" else "num_without"
    if metric.get("missing_members") and metric.get(without):
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
                cube_filters_for(checks["cube_filters"], metric.get("datasource")),
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
                metric.get("datasource"),
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
            cube_filters_for(checks["cube_filters"], checks["extract"]["datasource"]),
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
            checks["extract"]["datasource"],
        )
    ):
        value, n = norm_key(r["g0"]), r["n_students"]
        if n and not seen.get(value):
            raise ScopeError(
                f"Cube returned no {checks['scope_measure']} for {name}={value}, but the "
                f"warehouse has {n} students. The Cube identity's scope is narrower than "
                "the dashboard's; rerun as a network-scoped user."
            )


def _source(bq, datasource: str):
    """The truth source for a datasource: one callable for every extract, or one each."""
    return bq[datasource] if isinstance(bq, dict) else bq


def _merge_outcomes(outs: list[dict]) -> dict:
    """One grain's outcome across the extracts its row's metrics read."""
    if any(o["status"] == "not_comparable" for o in outs):
        return {"status": "not_comparable"}
    return {
        "status": "ok",
        "pre_aggregations": sorted({p for o in outs for p in o["pre_aggregations"]}),
        "metrics": {k: v for o in outs for k, v in o["metrics"].items()},
        "errors": {k: v for o in outs for k, v in o["errors"].items()},
    }


def run_dashboard(
    checks,
    cube_load,
    bq,
    today,
    rows=None,
    scope_only=False,
    snapshots=None,
    audit=None,
    workers=1,
) -> dict:
    window = resolve_window(checks, today)
    dims, hard = checks["dimensions"], checks["hard_filters"]
    scope_guard(checks, cube_load, _source(bq, checks["extract"]["datasource"]), window)
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

    # One Cube query and one SQL query per (view, extract, grain), carrying every metric.
    jobs: dict[tuple, list[dict]] = {}
    for row in selected:
        view = row.get("view", checks["view"])
        for g in row["grains"]:
            for m in row["metrics"]:
                metrics = jobs.setdefault((view, m["datasource"], tuple(g)), [])
                if m["key"] not in [x["key"] for x in metrics]:
                    metrics.append(m)

    truth_lock, progress = threading.Lock(), threading.Lock()
    finished = [0]
    accepted, rejected, open_issues = issue_states(checks)

    def say(text: str) -> None:
        with progress:
            finished[0] += 1
            print(f"[{finished[0]}/{len(jobs)}] {text}", file=sys.stderr, flush=True)

    def run_job(item):
        (view, ds, g), metrics = item
        grain = [dims[n] for n in g]
        label = f"{view} {_label(g)}"
        if ds != checks["extract"]["datasource"]:
            label += f" ({ds})"
        if any(d.cube is None for d in grain):
            say(f"{label}: not comparable")
            return (view, ds, g), {"status": "not_comparable"}
        source = _source(bq, ds)

        def truth(sql):
            # An extract connection serves one query at a time; Cube queries overlap.
            with truth_lock:
                return source(sql)

        def compare_job(ms):
            crows, preaggs = cube_load(
                cube_query(
                    view,
                    [m["cube"] for m in ms],
                    list(g),
                    dims,
                    hard,
                    window,
                    cube_filters_for(checks["cube_filters"], ds),
                )
            )
            trows = truth(
                truth_sql(
                    EXTRACT_TABLE,
                    ms,
                    list(g),
                    dims,
                    hard,
                    window,
                    checks["students_sql"],
                    checks["truth_filters"],
                    ds,
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
                # A variant the owner ruled cube-wrong explains nothing.
                alts = {
                    j: truth_cells(trows, len(g), i, m["kind"], f"_v{j}")
                    for j in range(len(m["variants"]))
                }
                variants = [
                    (v["explains"], alts[j])
                    for j, v in enumerate(m["variants"])
                    if not set(v["explains"]) & rejected
                ]
                explain(cells, m["kind"], variants)
                w = without_index(m)
                summaries[m["key"]] = summarize(
                    cells,
                    m["kind"],
                    None if w is None else alts[w],
                    accepted,
                    open_issues,
                )
            # A cell keyed by a person (a student or a teacher) never names them.
            person = {
                i: d.person if isinstance(d.person, str) else "a student"
                for i, d in enumerate(grain)
                if d.person
            }
            for s_ in summaries.values() if person else []:
                for c in [*s_["worst"], *s_["examples"]]:
                    c["key"] = [person.get(i, k) for i, k in enumerate(c["key"])]
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
                    errors[m["key"]] = f"{type(e1).__name__}: {e1}"[:300]
            if len(metrics) == 1:
                errors[metrics[0]["key"]] = f"{type(e).__name__}: {e}"[:300]
        outcome = {
            "status": "ok",
            "pre_aggregations": sorted(preaggs),
            "metrics": summaries,
            "errors": errors,
        }
        say(label)
        return (view, ds, g), outcome

    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=workers) as pool:
            outcomes = dict(pool.map(run_job, jobs.items()))
    else:
        outcomes = dict(run_job(item) for item in jobs.items())

    for row in selected:
        view = row.get("view", checks["view"])
        sources = list(dict.fromkeys(m["datasource"] for m in row["metrics"]))
        grains = []
        missing: dict[str, dict] = {}
        for g in row["grains"]:
            o = _merge_outcomes([outcomes[(view, ds, tuple(g))] for ds in sources])
            entry = {"grain": list(g), "status": o["status"]}
            if o["status"] == "error":
                entry["error"] = o["error"]
            if o["status"] == "not_comparable":
                for name in g:
                    if dims[name].cube is None and not dims[name].tableau_only:
                        _missing(missing, name)["blocks_grains"].append(_label(g))
            errs = [
                o["errors"][m["key"]]
                for m in row["metrics"]
                if m["key"] in o.get("errors", {})
            ]
            if errs:
                entry.update(status="error", error=errs[0])
            elif o["status"] == "ok":
                ms = {m["key"]: o["metrics"][m["key"]] for m in row["metrics"]}
                bad = sum(s["bad"] for s in ms.values())
                explained = sum(s["explained"] for s in ms.values())
                for m in row["metrics"]:
                    only = ms[m["key"]].get("only") or {}
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
                        mm["explains_cells"] += ms[m["key"]]["explained_by"].get(
                            name, 0
                        )
                        mm["changes_total"] = mm["changes_total"] or moves
                review = sum(s["review"] for s in ms.values())
                entry.update(
                    status="fail"
                    if bad
                    else "truth_issue"
                    if review
                    else ("missing_member" if explained else "pass"),
                    cells=sum(s["cells"] for s in ms.values()),
                    bad=bad,
                    explained=explained,
                    review=review,
                    accepted=sum(s["accepted"] for s in ms.values()),
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
            if m.get("diagnose_by") and m["key"] in failing:
                diagnosis[m["key"]] = _diagnose(
                    checks, cube_load, _source(bq, m["datasource"]), window, view, m
                )
        a = (audit or {}).get(str(row["row_gid"]), {})
        verdict = row_verdict(grains)
        if (a.get("unaccounted") or a.get("error")) and verdict in (
            "pass",
            "missing_member",
            "truth_issue",
        ):
            # A construct nobody accounted for may change what the sheet shows.
            verdict = "incomplete"
        truth = {}
        named = {
            n
            for m in row["metrics"]
            for v in m["variants"]
            for n in v["explains"]
            if n in checks["truth_issues"]
        }
        for slug in sorted(named):
            t = checks["truth_issues"][slug]
            n = sum(
                s["explained_by"].get(slug, 0)
                for g in grains
                for s in g.get("metrics", {}).values()
            )
            truth[slug] = {
                "explains_cells": n,
                "issue": t.get("issue"),
                "ruling": (t.get("ruling") or {}).get("call"),
                # A closed issue that explains nothing any more: remove its entry.
                "stale": bool(t.get("closed_on")) and not n,
            }
        result["rows"][str(row["row_gid"])] = {
            "name": row["name"],
            "verdict": verdict,
            "grains": grains,
            **({"diagnosis": diagnosis} if diagnosis else {}),
            **({"truth_issues": truth} if truth else {}),
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
        causes = ", ".join(s_.get("explained_by") or {}) or ", ".join(members)
        lines = [f"- Total differs, explained by {causes}: Cube {c}, Tableau {t}."]
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


_COMPARED = ("pass", "fail", "missing_member", "truth_issue")


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


def _construct_hint(c: dict) -> str:
    """One short phrase on what a construct does, for the digest."""
    d, k = c.get("detail") or {}, c["kind"]
    if k == "group":
        return (
            f"{len(d.get('bins', {}))} bins over {d.get('of') or d.get('of_formula')}"
        )
    if k == "bin":
        return f"size {d.get('size')} over {d.get('of')}"
    if k in ("filter", "set", "source_filter"):
        bits = [d.get("mode", "include")]
        if d.get("members"):
            # A count, never the values: a filter's members can be student names.
            n = d["members"] if isinstance(d["members"], int) else len(d["members"])
            bits.append(_plural(n, "member"))
        if d.get("range"):
            bits.append(", ".join(f"{a} {v}" for a, v in d["range"].items()))
        if d.get("context"):
            bits.append("context")
        return "; ".join(bits)
    if k == "alias":
        return f"shows {d.get('field')}"
    for key in ("quick", "formula", "expressions", "start_month"):
        if d.get(key):
            return str(d[key])
    return ""


def _construct_lines(items: list[dict], with_why: bool) -> list[str]:
    out = []
    for c in items:
        hint = _construct_hint(c)
        line = f"- {c['ref']} on {', '.join(c['sheets'])}"
        line += f" ({hint})" if hint else ""
        line += f": {c['why']}" if with_why else ""
        out.append(line)
    return out


def _issue_ref(t: dict) -> str:
    return f"#{t['issue']}" if t.get("issue") else "draft"


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
    owner = [
        f"{slug} ({_issue_ref(t)}, {t['explains_cells']} cells)"
        for slug, t in row.get("truth_issues", {}).items()
        if t["explains_cells"] and not t["ruling"]
    ]
    if owner:
        lines.append(f"Dashboard issues for the domain owner: {', '.join(owner)}.")
    wrong = [
        f"{slug} ({_issue_ref(t)})"
        for slug, t in row.get("truth_issues", {}).items()
        if t["ruling"] == "cube-wrong"
    ]
    if wrong:
        lines.append(f"Ruled cube-wrong, so Cube must change: {', '.join(wrong)}.")
    if bad:
        n = sum(1 for g in compared if g["bad"])
        lines.append(
            f"Investigate: {bad} cells across {_plural(n, 'grain')}; details in the "
            f"{result['dashboard']} fix digest."
        )
    elif row["verdict"] in ("missing_member", "truth_issue"):
        lines.append("Nothing else to investigate.")
    elif row["verdict"] == "pass":
        lines.append("Every compared cell matches.")
    errors = [g for g in grains if g["status"] == "error"]
    if errors:
        lines.append(
            f"Could not compare {_plural(len(errors), 'grain')}: {errors[0]['error']}"
        )
    if row.get("audit_error"):
        lines.append(f"Not audited: {row['audit_error']}.")
    if row.get("unaccounted"):
        lines.append(
            f"Unaccounted Tableau constructs: {len(row['unaccounted'])}; "
            "see the fix digest."
        )
    if row.get("not_checked"):
        lines.append(
            f"Not checked: {_plural(len(row['not_checked']), 'Tableau construct')}; "
            "see the fix digest."
        )
    return "\n".join(lines)


def _cell_text(c: dict, kind: str) -> str:
    if c["n_students"] is None or c["n_students"] < SMALL_CELL:
        return "small cell"
    return f"Cube {_fmt(c['cube'], kind)}, Tableau {_fmt(c['truth'], kind)}"


def _metric_sql(m: dict, without: bool = False) -> str:
    if without and not m.get("sql_without" if m["kind"] == "count" else "num_without"):
        w = without_index(m)
        if w is None:
            return "(no SQL without it)"
        return _metric_sql({**m["variants"][w], "kind": m["kind"]})
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
    ]
    issues: dict[str, dict] = {}
    for gid, row in rows.items():
        for slug, t in row.get("truth_issues", {}).items():
            i = issues.setdefault(slug, {"cells": 0, "rows": [], "stale": True, **t})
            i["cells"] += t["explains_cells"]
            i["stale"] = i["stale"] and t["stale"]
            if t["explains_cells"]:
                i["rows"].append(gid)
    shown = {
        s: i
        for s, i in issues.items()
        if i["cells"] or i["stale"] or i.get("ruling") == "cube-wrong"
    }
    if shown:
        out += ["## Dashboard, model or source issues", ""]
        stem = f"{result['run_date']}-{result['dashboard']}"
        for slug, i in sorted(shown.items(), key=lambda kv: -kv[1]["cells"]):
            doc = (checks.get("truth_issues") or {}).get(slug, {})
            names = ", ".join(rows[g]["name"] for g in i["rows"])
            out.append(
                f"### {slug} ({doc.get('where', '?')}): explains "
                f"{_plural(i['cells'], 'cell')} in {_plural(len(i['rows']), 'row')}"
                + (f" ({names})" if names else "")
            )
            if doc.get("title"):
                out.append(f"- {doc['title']}")
            if doc.get("what"):
                out.append(f"- What: {doc['what']}")
            if i["stale"]:
                out.append(
                    "- Stale: the issue is closed and explains no cell now; "
                    "remove its entry."
                )
            elif i.get("issue"):
                call = (
                    f", ruled {i['ruling']}" if i.get("ruling") else ", not ruled yet"
                )
                out.append(f"- Issue: #{i['issue']}{call}")
            else:
                out.append(f"- Draft: `{stem}-issues/{slug}.md`")
            out.append("")
    out += ["## Add to Cube", ""]
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
        dims_ = checks["dimensions"]
        rules = {
            n: b
            for n, b in blocked.items()
            if getattr(dims_.get(n), "group_kind", None) == "rule"
        }
        plain = {n: b for n, b in blocked.items() if n not in rules}
        for title, group in (
            ("Dimensions the dashboard slices by that Cube lacks", plain),
            # A group that encodes a definition: someone decides it, then Cube names it.
            ("Definitions to decide", rules),
        ):
            if not group:
                continue
            out += [f"### {title}", ""]
            for name, b in sorted(group.items(), key=lambda kv: -kv[1]["grains"]):
                dim = dims_.get(name)
                col = f"; dashboard field `{dim.sql}`" if dim else ""
                out.append(
                    f"- {name}: blocks {_plural(b['grains'], 'grain')} in "
                    f"{_plural(b['rows'], 'row')}{col}"
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
                (x for x in defs.get(gid, {}).get("metrics", []) if x["key"] == m),
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
                    if x["key"] == m
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
            out.append(f"- Dashboard: {m['key']} = {_metric_sql(m)}")
            cdef = (cube_defs or {}).get(m["cube"])
            out.append(f"- Cube: {_cube_text(m['cube'], cdef)}")
            for r in (cdef or {}).get("refs", []):
                out.append(f"  - uses {_cube_text(r['name'], r)}")
        out.append("")
    if not any_gap:
        out += ["Nothing unexplained.", ""]
    gaps = [
        (g, r) for g, r in rows.items() if r.get("unaccounted") or r.get("audit_error")
    ]
    if gaps:
        out += [
            "## Unaccounted Tableau constructs",
            "",
            "Add each to the checks file: under `handled:` with what reproduces it, "
            "or under the row's `not_checked:` with why.",
            "",
        ]
        for gid, r in gaps:
            out.append(f"### {r['name']} ({gid})")
            if r.get("audit_error"):
                out.append(f"- Not audited: {r['audit_error']}")
            out += _construct_lines(r.get("unaccounted", []), with_why=False)
            out.append("")
    skipped = [(g, r) for g, r in rows.items() if r.get("not_checked")]
    if skipped:
        out += ["## Not checked", ""]
        for gid, r in skipped:
            out.append(f"### {r['name']} ({gid})")
            out += _construct_lines(r["not_checked"], with_why=True)
            out.append("")
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
        if row.get("truth_issues"):
            parts = [
                f"{s} ({t['explains_cells']} cells; {_issue_ref(t)}"
                + (f"; {t['ruling']}" if t["ruling"] else "")
                + ")"
                for s, t in row["truth_issues"].items()
            ]
            out += [f"Truth issues: {', '.join(parts)}.", ""]
        for label, key in (
            ("Unaccounted", "unaccounted"),
            ("Not checked", "not_checked"),
        ):
            if row.get(key):
                out += [f"{label}: {', '.join(c['ref'] for c in row[key])}.", ""]
        if row.get("audit_error"):
            out += [f"Not audited: {row['audit_error']}.", ""]
        for g in row["grains"]:
            line = f"- {_label(g['grain'])}: {g['status']}"
            if g["status"] in _COMPARED:
                line += f", {g['bad']} of {g['cells']} cells out of tolerance"
                if g.get("explained"):
                    line += f", {g['explained']} explained by missing members"
                if g.get("review"):
                    line += f", {g['review']} awaiting the domain owner"
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


def draft_sql(m: dict, v: dict, checks: dict, window) -> str:
    """The dashboard's calculation and its correction, side by side, over the warehouse."""
    try:
        table = live_table(m["datasource"])
    except CheckError:
        table = m["datasource"]
    if m["kind"] == "count":
        cols = [f"{m['sql']} as as_written", f"{v['sql']} as corrected"]
    else:
        cols = [
            f"{m['num']} as as_written_num",
            f"{m['den']} as as_written_den",
            f"{v['num']} as corrected_num",
            f"{v['den']} as corrected_den",
        ]
    where = _truth_where(
        checks["dimensions"],
        checks["hard_filters"],
        window,
        checks["truth_filters"],
        m["datasource"],
        public_only=True,
    )
    # trunk-ignore(bandit/B608): SQL comes from a reviewed checks file and runs read-only
    return f"select {', '.join(cols)}\nfrom `{table}`\nwhere " + "\n  and ".join(where)


def _issue_labels(t: dict) -> list[str]:
    kind = re.match(r"^([a-z]+)", t["title"])
    labels = [kind.group(1)] if kind else []
    labels += {"dashboard": ["tableau"], "rpt": ["dbt"]}.get(t["where"], [])
    return list(dict.fromkeys([*labels, *t["labels"], "validation"]))


def _example_text(c: dict) -> str:
    if c["n_students"] is None or c["n_students"] < SMALL_CELL:
        return "small cell"
    k = c["kind"]
    return (
        f"the dashboard shows {_fmt(c['truth'], k)}, the corrected calculation gives "
        f"{_fmt(c['variant'], k)}, and Cube gives {_fmt(c['cube'], k)}"
    )


def issue_drafts(result, checks) -> dict[str, dict]:
    """One GitHub issue draft per unfiled truth issue that explains cells."""
    window = resolve_window(checks, dt.date.fromisoformat(result["run_date"]))
    out = {}
    for slug, t in (checks.get("truth_issues") or {}).items():
        hits = [
            (gid, row)
            for gid, row in result["rows"].items()
            if row.get("truth_issues", {}).get(slug, {}).get("explains_cells")
        ]
        if t.get("issue") or not hits:
            continue
        cells = sum(row["truth_issues"][slug]["explains_cells"] for _, row in hits)
        m, v = next(
            (m, v)
            for r in checks["rows"]
            for m in r["metrics"]
            for v in m["variants"]
            if slug in v["explains"]
        )
        # The coarsest grains first: a total reads more plainly than a classroom.
        examples = sorted(
            (
                (len(g["grain"]), c)
                for _, row in hits
                for g in row["grains"]
                for s in g.get("metrics", {}).values()
                for c in s.get("examples", [])
                if slug in c["explains"]
            ),
            key=lambda x: x[0],
        )[:3]
        rows_text = ", ".join(f"{row['name']} ({gid})" for gid, row in hits)
        place = {
            "dashboard": f"the Tableau workbook behind {result['dashboard']}",
            "rpt": f"the kipptaf dbt model behind `{m['datasource']}`",
            "source": f"the source data feeding `{m['datasource']}`",
        }[t["where"]]
        body = [
            "## What's happening",
            "",
            t["what"],
            "",
            f"The cube-dashboard validation compared Cube with {result['dashboard']}'s "
            f"extract on {result['run_date']}. With the dashboard's calculation "
            f"corrected, Cube matches it in {_plural(cells, 'cell')} across "
            f"{_plural(len(hits), 'row')}.",
            "",
            *[
                f"- {' / '.join(c['key']) or 'All'}: {_example_text(c)}."
                for _, c in examples
            ],
            *(["", t["evidence"]] if t.get("evidence") else []),
            "",
            "## Steps to reproduce",
            "",
            "1. Run this query in BigQuery. `as_written` is the dashboard's "
            "calculation and `corrected` is the fix.",
            "",
            "   ```sql",
            *[f"   {line}" for line in draft_sql(m, v, checks, window).splitlines()],
            "   ```",
            "",
            f"2. Compare both with Cube's `{checks['view']}.{m['cube']}` over the "
            "same filters. Cube matches `corrected`.",
            "",
            "## Where",
            "",
            f"- **Code location / dbt project:** {place}",
            "- **Environment:** prod",
            f"- **Run, PR, or dashboard link (if any):** Asana rows {rows_text}",
            "",
            "## How to answer",
            "",
            "Add one label from the Labels menu on the right of this issue, or, "
            "if you cannot add labels, write a comment that starts with the word. "
            "`cube-correct` means the dashboard is wrong and Cube's number is "
            "right. `cube-wrong` means the dashboard is right and Cube must "
            "change. If you fix the dashboard or the model instead, close this "
            "issue; the next validation run checks the fix.",
            "",
            "<details>",
            "<summary>For Claude</summary>",
            "",
            f"> Checks file `.claude/skills/cube-dashboard/checks/"
            f"{Path(checks['path']).name}`, truth issue `{slug}`. As written: "
            f"{_metric_sql(m)}. Corrected: {_metric_sql({**v, 'kind': m['kind']})}. "
            "Digest: the run's `-fixes.md` under `~/asana-sync/validation/`.",
            "",
            "</details>",
        ]
        out[slug] = {
            "title": t["title"],
            "labels": _issue_labels(t),
            "body": "\n".join(body),
        }
    return out


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
    drafts = issue_drafts(result, checks) if checks else {}
    for slug, d in drafts.items():
        issues_dir = out_dir / f"{stem}-issues"
        issues_dir.mkdir(exist_ok=True)
        (issues_dir / f"{slug}.md").write_text(
            f"Title: {d['title']}\nLabels: {', '.join(d['labels'])}\n\n{d['body']}\n"
        )
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
            "truth_issues": sorted(
                s
                for s, t in row.get("truth_issues", {}).items()
                if t["explains_cells"] and not t["ruling"]
            ),
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
    datasources = list(
        dict.fromkeys(
            [checks["extract"]["datasource"]]
            + [m["datasource"] for r in checks["rows"] for m in r["metrics"]]
        )
    )
    print(
        f"downloading the workbook's {len(datasources)} extract(s)",
        file=sys.stderr,
        flush=True,
    )
    extracts = download_extract(
        checks["extract"]["workbook_luid"], datasources, SCRATCH / checks["dashboard"]
    )
    cube_at = cube_built_at(checks["cube_source_table"], bigquery_rows)
    audit = audit_rows(checks, SCRATCH / checks["dashboard"] / "workbook.twb")
    checks["truth_filters"] = checks["truth_filters"] + workbook_exclusions(
        checks, SCRATCH / checks["dashboard"] / "workbook.twb"
    )
    from contextlib import ExitStack

    default_at = extracts[checks["extract"]["datasource"]][1]
    stamps = "; ".join(
        _local(at) if len(extracts) == 1 else f"{ds} {_local(at)}"
        for ds, (_, at) in extracts.items()
    )
    today = dt.date.today()
    closed = window_is_closed(resolve_window(checks, today), today)
    cube_stamp = _local(cube_at)
    if checks.get("settle"):
        # Scores still being entered sit inside the settle window: leave them out on
        # both sides, and the snapshots no longer need to be close in time.
        truth, cube_settle = settle_filters(checks, snapshot_date(default_at))
        checks["truth_filters"] = [*checks["truth_filters"], truth]
        checks["cube_filters"] = [*checks["cube_filters"], *cube_settle]
        cube_stamp += (
            f" (scores from the last {checks['settle']['days']} days left out)"
        )
    elif closed:
        cube_stamp += " (closed year: timing not checked)"
    try:
        for _, at in extracts.values() if not (closed or checks.get("settle")) else []:
            timing_guard(at, cube_at)
        with ExitStack() as stack:
            truth = {
                ds: stack.enter_context(ExtractSource(hyper))
                for ds, (hyper, _) in extracts.items()
            }
            result = run_dashboard(
                checks,
                cube.load,
                truth,
                snapshot_date(default_at),
                rows=set(a.rows.split(",")) if a.rows else None,
                scope_only=a.scope_only,
                snapshots={"extract": stamps, "cube": cube_stamp},
                audit=audit,
                workers=a.workers,
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
    drafts = a.out / f"{report.stem}-issues"
    if drafts.exists():
        print(f"issue drafts: {drafts}")
    for gid, row in result["rows"].items():
        print(f"{row['verdict']:<10} {gid} {row['name']}")
    print(f"report: {report}")
    return 0 if all(r["verdict"] == "pass" for r in result["rows"].values()) else 1


def _settle_command(a) -> int:
    checks = load_checks(a.checks)
    if not (checks.get("settle") or {}).get("date"):
        sys.exit(
            f"{a.checks}: add settle.date (the SQL for a row's date) before measuring"
        )
    datasources = list(
        dict.fromkeys(m["datasource"] for r in checks["rows"] for m in r["metrics"])
    )
    try:
        tables = {ds: live_table(ds) for ds in datasources}
    except CheckError as e:
        sys.exit(str(e))
    extracts = download_extract(
        checks["extract"]["workbook_luid"], datasources, SCRATCH / checks["dashboard"]
    )
    checks["truth_filters"] = checks["truth_filters"] + workbook_exclusions(
        checks, SCRATCH / checks["dashboard"] / "workbook.twb"
    )
    default_at = extracts[checks["extract"]["datasource"]][1]
    window = resolve_window(checks, snapshot_date(default_at))
    now = dt.datetime.now(default_at.tzinfo)
    recommend, oldest = 1, None
    for ds in datasources:
        hyper, at = extracts[ds]
        with ExtractSource(hyper) as q:
            ext = q(settle_sql(checks, ds, EXTRACT_TABLE, window))
        live = bigquery_rows(settle_sql(checks, ds, tables[ds], window))
        drift = settle_drift(ext, live, snapshot_date(at))
        print(settle_text(ds, drift, _settle_labels(checks, ds)))
        recommend = max(recommend, drift["recommend"])
        if drift["oldest_age"] is not None:
            oldest = max(oldest or 0, drift["oldest_age"])
    hours = round((now - default_at).total_seconds() / 3600)
    print(
        f"\n# settle measured {now.date()}: live tables {hours} hours after the "
        "extract refresh; oldest change "
        + (f"{oldest} days before it" if oldest is not None else "none")
        + f"; days {recommend}"
    )
    return 0


def _snippet(c: Construct) -> dict:
    """A checks-file dimension to paste for a group or bin on a plain column."""
    d = c.detail
    if c.kind == "group" and d.get("of"):
        return {
            "dimension": {
                "group": {"of": d["of"], "bins": d["bins"]},
                "kind": "relabel or rule: decide",
                "cube": None,
            }
        }
    if c.kind == "bin" and d.get("of"):
        return {"dimension": {"bin": {"of": d["of"], "size": d["size"]}, "cube": None}}
    return {}


def _sheet_out(s: Sheet) -> dict:
    """A sheet for `grains` output, its constructs redacted like every other output."""
    out = asdict(s)
    out["constructs"] = [_public(c) for c in s.constructs]
    return out


def _grains_command(a) -> int:
    sheets = parse_twb(a.twb, a.dashboard)
    if a.measure:
        measure: str = a.measure
        using = [
            s
            for s in sheets
            if a.measure in s.measures or a.measure in s.measure_aliases
        ]
        out = {
            "measure": a.measure,
            "resolves_to": sorted(
                {s.measure_aliases.get(measure, measure) for s in using}
            ),
            "sheets": [_sheet_out(s) for s in using],
            "grains": propose_grains(sheets, a.measure),
            "constructs": [
                dict(_public(c), **_snippet(c)) for c in merge_constructs(using)
            ],
        }
    else:
        out = {"sheets": [_sheet_out(s) for s in sheets]}
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
    r.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Cube queries in flight at once (default 4; 1 runs them in order)",
    )
    r.add_argument("--out", type=Path, default=DEFAULT_OUT)
    s = sub.add_parser(
        "settle", help="measure how many days before a refresh scores still change"
    )
    s.add_argument("checks")
    a = p.parse_args(argv)
    commands = {
        "grains": _grains_command,
        "run": _run_command,
        "settle": _settle_command,
    }
    return commands[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
