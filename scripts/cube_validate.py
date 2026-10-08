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
import re
import sys
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


# ---------------------------------------------------------------- checks files and queries
CUBE_LIMIT = 50_000
KINDS = {"count", "rate"}


class CheckError(ValueError):
    """A checks file that cannot be run as written."""


@dataclass(frozen=True)
class Dim:
    name: str
    cube: str | None  # None: no Cube member, so grains using it are not comparable
    sql: str
    granularity: str | None = None


def load_checks(path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    for key in ("dashboard", "table", "view", "dimensions", "rows"):
        if key not in data:
            raise CheckError(f"{path}: missing '{key}'")
    dims = {
        n: Dim(n, d.get("cube"), d["sql"], d.get("granularity"))
        for n, d in data["dimensions"].items()
    }
    if "date" not in dims or not dims["date"].cube:
        raise CheckError(
            f"{path}: 'dimensions.date' needs a cube member and a sql column"
        )
    for d in dims.values():
        if d.granularity and d.cube != dims["date"].cube:
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
        for g in row["grains"]:
            unknown = [n for n in g if n not in dims]
            if unknown:
                raise CheckError(
                    f"{where}: grain {g} uses unknown dimension(s) {unknown}"
                )
            if sum(1 for n in g if dims[n].granularity) > 1:
                raise CheckError(f"{where}: grain {g} has more than one date part")
    data["dimensions"] = dims
    data.setdefault("scope_measure", "count_students")
    data.setdefault("students_sql", "count(distinct student_number)")
    return data


def academic_window(today: dt.date) -> tuple[dt.date, dt.date]:
    """July 1 of the academic year that contains yesterday, through yesterday."""
    end = today - dt.timedelta(days=1)
    return dt.date(end.year if end.month >= 7 else end.year - 1, 7, 1), end


def cube_key(view: str, dim: Dim) -> str:
    return (
        f"{view}.{dim.cube}.{dim.granularity}"
        if dim.granularity
        else f"{view}.{dim.cube}"
    )


def cube_query(view, measures, grain, dims, hard_filters, window) -> dict:
    td = {
        "dimension": f"{view}.{dims['date'].cube}",
        "dateRange": [window[0].isoformat(), window[1].isoformat()],
    }
    plain = []
    for name in grain:
        d = dims[name]
        if d.granularity:
            td["granularity"] = d.granularity
        else:
            plain.append(f"{view}.{d.cube}")
    return {
        "measures": [f"{view}.{m}" for m in measures],
        "dimensions": plain,
        "timeDimensions": [td],
        "filters": [
            {
                "member": f"{view}.{dims[f['dim']].cube}",
                "operator": "equals",
                "values": [str(v) for v in f["values"]],
            }
            for f in hard_filters
        ],
        "limit": CUBE_LIMIT,
        "timezone": "UTC",
    }


def _sql_literal(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v)
    return "'" + str(v).replace("'", "\\'") + "'"


def truth_sql(table, metrics, grain, dims, hard_filters, window, students_sql) -> str:
    select = [f"{dims[n].sql} as g{i}" for i, n in enumerate(grain)]
    for i, m in enumerate(metrics):
        if m["kind"] == "count":
            select.append(f"{m['sql']} as m{i}")
        else:
            select += [f"{m['num']} as m{i}_num", f"{m['den']} as m{i}_den"]
    select.append(f"{students_sql} as n_students")
    where = [f"{dims['date'].sql} between '{window[0]}' and '{window[1]}'"]
    for f in hard_filters:
        values = ", ".join(_sql_literal(v) for v in f["values"])
        where.append(f"{dims[f['dim']].sql} in ({values})")
    # trunk-ignore(bandit/B608): SQL comes from a reviewed checks file and runs read-only
    sql = f"select {', '.join(select)} from `{table}` where {' and '.join(where)}"
    if grain:
        sql += " group by " + ", ".join(str(i + 1) for i in range(len(grain)))
    return sql


# ---------------------------------------------------------------- comparison
SMALL_CELL = 10
RATE_TOLERANCE = 0.001
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


def truth_cells(rows, n_grain, i, kind) -> dict:
    out = {}
    for r in rows:
        key = tuple(norm_key(r[f"g{j}"]) for j in range(n_grain))
        if kind == "count":
            v = _num(r[f"m{i}"])
        else:
            num, den = _num(r[f"m{i}_num"]), _num(r[f"m{i}_den"])
            v = None if not den else (num or 0.0) / den
        n = r.get("n_students")
        out[key] = (v, None if n is None else int(n))
    return out


def compare(kind, cube, truth) -> list[Cell]:
    cells = []
    for key in sorted(set(cube) | set(truth)):
        c = cube.get(key)
        t, n = truth.get(key, (None, None))
        if kind == "count":
            # No row on a side means nothing to count there: compare as 0.
            c, t = c or 0.0, t or 0.0
            ok = abs(c - t) < 1e-9
        else:
            ok = (c is None and t is None) or (
                c is not None and t is not None and abs(c - t) <= RATE_TOLERANCE + 1e-12
            )
        cells.append(Cell(key, c, t, n, ok))
    return cells


def summarize(cells, kind) -> dict:
    bad = sorted((c for c in cells if not c.ok), key=lambda c: -c.delta)
    return {
        "cells": len(cells),
        "bad": len(bad),
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
    if "error" in statuses or "pass" not in statuses:
        return "incomplete"
    return "pass"


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
