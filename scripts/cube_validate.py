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
    tableau_only: bool = False  # a dashboard control, not data: never a missing member


def load_checks(path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    for key in ("dashboard", "table", "view", "dimensions", "rows"):
        if key not in data:
            raise CheckError(f"{path}: missing '{key}'")
    dims = {
        n: Dim(
            n,
            d.get("cube"),
            d["sql"],
            d.get("granularity"),
            bool(d.get("tableau_only")),
        )
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
        for g in row["grains"]:
            unknown = [n for n in g if n not in dims]
            if unknown:
                raise CheckError(
                    f"{where}: grain {g} uses unknown dimension(s) {unknown}"
                )
            if sum(1 for n in g if dims[n].granularity) > 1:
                raise CheckError(f"{where}: grain {g} has more than one date part")
    data["dimensions"] = dims
    # Cube-side only: what the dashboard's table already excludes (e.g. break days).
    data.setdefault("cube_filters", [])
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


def cube_query(
    view, measures, grain, dims, hard_filters, window, cube_filters=()
) -> dict:
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
        ]
        + [dict(f, member=f"{view}.{f['member']}") for f in cube_filters],
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
        if m.get("missing_members") and m["kind"] == "count":
            select.append(f"{m['sql_without']} as m{i}_alt")
        elif m.get("missing_members"):
            select += [
                f"{m['num_without']} as m{i}_alt_num",
                f"{m['den_without']} as m{i}_alt_den",
            ]
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
        c is not None and t is not None and abs(c - t) <= RATE_TOLERANCE + 1e-12
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


def summarize(cells, kind) -> dict:
    bad = sorted(
        (c for c in cells if not c.ok and not c.explained), key=lambda c: -c.delta
    )
    return {
        "cells": len(cells),
        "bad": len(bad),
        "explained": sum(1 for c in cells if c.explained),
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


# ---------------------------------------------------------------- run
def _missing(missing: dict, name: str) -> dict:
    return missing.setdefault(name, {"explains_cells": 0, "blocks_grains": []})


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
            checks["table"], [], [name], dims, hard, window, checks["students_sql"]
        )
    ):
        value, n = norm_key(r["g0"]), r["n_students"]
        if n and not seen.get(value):
            raise ScopeError(
                f"Cube returned no {checks['scope_measure']} for {name}={value}, but the "
                f"warehouse has {n} students. The Cube identity's scope is narrower than "
                "the dashboard's; rerun as a network-scoped user."
            )


def run_dashboard(checks, cube_load, bq, today, rows=None, scope_only=False) -> dict:
    window = academic_window(today)
    dims, hard = checks["dimensions"], checks["hard_filters"]
    scope_guard(checks, cube_load, bq, window)
    result = {
        "dashboard": checks["dashboard"],
        "window": [window[0].isoformat(), window[1].isoformat()],
        "run_date": today.isoformat(),
        "rows": {},
    }
    if scope_only:
        return result
    selected = [r for r in checks["rows"] if rows is None or str(r["row_gid"]) in rows]

    # One Cube query and one SQL query per (view, table, grain), carrying every metric.
    jobs: dict[tuple, list[dict]] = {}
    for row in selected:
        where = (row.get("view", checks["view"]), row.get("table", checks["table"]))
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
        try:
            crows, preaggs = cube_load(
                cube_query(
                    view,
                    [m["cube"] for m in metrics],
                    list(g),
                    dims,
                    hard,
                    window,
                    checks["cube_filters"],
                )
            )
            trows = bq(
                truth_sql(
                    table, metrics, list(g), dims, hard, window, checks["students_sql"]
                )
            )
        except Exception as e:  # noqa: BLE001 - any failure leaves this grain incomplete
            outcomes[(view, table, g)] = {
                "status": "error",
                "error": f"{type(e).__name__}: {e}"[:300],
            }
            continue
        summaries = {}
        for i, m in enumerate(metrics):
            cells = compare(
                m["kind"],
                cube_cells(crows, view, grain, m["cube"]),
                truth_cells(trows, len(g), i, m["kind"]),
            )
            if m.get("missing_members"):
                explain(
                    cells, m["kind"], truth_cells(trows, len(g), i, m["kind"], "_alt")
                )
            summaries[m["cube"]] = summarize(cells, m["kind"])
        outcomes[(view, table, g)] = {
            "status": "ok",
            "pre_aggregations": preaggs,
            "metrics": summaries,
        }

    for row in selected:
        where = (row.get("view", checks["view"]), row.get("table", checks["table"]))
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
            if o["status"] == "ok":
                ms = {m["cube"]: o["metrics"][m["cube"]] for m in row["metrics"]}
                bad = sum(s["bad"] for s in ms.values())
                explained = sum(s["explained"] for s in ms.values())
                for m in row["metrics"]:
                    for name in m.get("missing_members", []):
                        _missing(missing, name)["explains_cells"] += ms[m["cube"]][
                            "explained"
                        ]
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
        result["rows"][str(row["row_gid"])] = {
            "name": row["name"],
            "verdict": row_verdict(grains),
            "grains": grains,
            "missing_members": {
                k: v
                for k, v in missing.items()
                if v["explains_cells"] or v["blocks_grains"]
            },
        }
    return result


# ---------------------------------------------------------------- outputs
def _fmt(v, kind) -> str:
    if v is None:
        return "none"
    return f"{v * 100:.1f}%" if kind == "rate" else f"{v:,.0f}"


def _label(grain) -> str:
    return " x ".join(grain) or "total"


def _where(grain, key) -> str:
    return f"{_label(grain)}, {' / '.join(key) or 'all'}"


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


def comment_text(row, result, report_path) -> str:
    grains = row["grains"]
    compared = [g for g in grains if g["status"] in _COMPARED]
    explained = sum(g.get("explained", 0) for g in compared)
    verdict = row["verdict"].replace("_", " ").upper()
    lines = [
        f"Cube vs Tableau check, {result['run_date']}: {verdict}",
        f"Window: {result['window'][0]} to {result['window'][1]}. {len(compared)} grains, "
        f"{sum(g['cells'] for g in compared)} cells, "
        f"{sum(g['bad'] for g in compared)} out of tolerance"
        + (f", {explained} explained by missing Cube members." if explained else "."),
    ]
    worst = None
    for g in compared:
        for metric, s in g["metrics"].items():
            for c in s["worst"][:1]:
                d = (
                    float("inf")
                    if c["cube"] is None or c["truth"] is None
                    else abs(c["cube"] - c["truth"])
                )
                # A cell big enough to report beats a bigger gap in a tiny one.
                rank = ((c["n_students"] or 0) >= SMALL_CELL, d)
                if worst is None or rank > worst[0]:
                    worst = (rank, g["grain"], metric, c)
    if worst:
        _, grain, metric, c = worst
        if c["n_students"] is None or c["n_students"] < SMALL_CELL:
            lines.append(
                f"Worst: {metric} at {_where(grain, c['key'])}: small cell, values in the report."
            )
        else:
            lines.append(
                f"Worst: {metric} at {_where(grain, c['key'])}: "
                f"Cube {_fmt(c['cube'], c['kind'])}, Tableau {_fmt(c['truth'], c['kind'])}."
            )
    if row.get("missing_members"):
        lines.append(f"Missing Cube members: {_missing_text(row['missing_members'])}.")
    lines += [
        f"Error at {_label(g['grain'])}: {g['error']}"
        for g in grains
        if g["status"] == "error"
    ]
    lines.append(f"Report: {report_path}")
    return "\n".join(lines)


def report_markdown(result) -> str:
    out = [
        f"# Cube vs Tableau: {result['dashboard']}",
        "",
        f"Run {result['run_date']}, window {result['window'][0]} to {result['window'][1]}.",
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


def write_outputs(result, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{result['run_date']}-{result['dashboard']}"
    report = out_dir / f"{stem}.md"
    for row in result["rows"].values():
        row["comment"] = comment_text(row, result, report)
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
    result = run_dashboard(
        checks,
        cube.load,
        bigquery_rows,
        dt.date.today(),
        rows=set(a.rows.split(",")) if a.rows else None,
        scope_only=a.scope_only,
    )
    if a.scope_only:
        print("scope ok")
        return 0
    report = write_outputs(result, a.out)
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
