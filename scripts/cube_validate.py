"""The Cube side of Cube validation: compare, explain, report.

    uv run --with tableauhyperapi scripts/cube_validate.py compare <checks.yml>
    uv run --with tableauhyperapi scripts/cube_validate.py explain <checks.yml>
    uv run --with tableauhyperapi scripts/cube_validate.py drafts <checks.yml>

Reads the latest snapshot cube_validate_snapshot.py wrote. `compare` and
`explain` need CUBE_API_SECRET, which only the pytest secrets fixture provides,
so they run inside a throwaway tests/test_zz_*.py. `explain` also reads the live
`rpt_` tables in BigQuery through ADC.
Runbook: .claude/skills/cube-dashboard/SKILL.md.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

CUBE_LIMIT = 50_000


DEFAULT_CUBE_URL = (
    "https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1"
)
USER_EMAIL_CACHE = Path.home() / ".config" / "teamster" / "cube-user-email"
DEFAULT_OUT = Path.home() / "asana-sync" / "validation"
BQ_PROJECT = "teamster-332318"


class CheckError(ValueError):
    """A checks file that cannot be run as written."""


FIX_SIDES = ("cube", "dashboard", "source", "undecided")


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


def _filtered(sql: str, cond: str) -> str:
    """A metric's SQL with every aggregate limited to the rows where `cond` holds."""
    import sqlglot
    from sqlglot import exp

    tree = sqlglot.parse_one(sql, read="bigquery")
    c = sqlglot.parse_one(cond, read="bigquery")

    def keep(x):
        return exp.If(this=c.copy(), true=x, false=exp.Null())

    for agg in list(tree.find_all(exp.AggFunc)):
        if isinstance(agg, exp.CountIf):
            agg.set("this", exp.and_(c.copy(), agg.this))
        elif isinstance(agg, exp.Count) and (
            agg.this is None or isinstance(agg.this, exp.Star)
        ):
            new = exp.CountIf(this=c.copy())
            # The aggregate may be the whole expression, which replace() cannot swap.
            if agg is tree:
                tree = new
            else:
                agg.replace(new)
        elif isinstance(agg.this, exp.Distinct):
            agg.this.set("expressions", [keep(e) for e in agg.this.expressions])
        else:
            agg.set("this", keep(agg.this))
    return tree.sql(dialect="bigquery")


def fix_sides(checks) -> dict[str, frozenset]:
    """Mismatch slugs by who fixes them: cube, dashboard, or undecided."""
    by: dict[str, set] = {side: set() for side in FIX_SIDES}
    for slug, t in (checks.get("mismatches") or {}).items():
        by[t["fix"]].add(slug)
    return {side: frozenset(v) for side, v in by.items()}


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
        self.last_refresh: str | None = None

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
            self.last_refresh = body.get("lastRefreshTime")
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


EXTRACT_TABLE = "EXTRACT_TABLE"  # truth_sql's table; to_hyper_sql names the extract's


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


def _user_email(given: str | None) -> str:
    email = (given or os.environ.get("CUBE_USER_EMAIL", "")).strip()
    if not email and USER_EMAIL_CACHE.exists():
        email = USER_EMAIL_CACHE.read_text().strip()
    if not email:
        sys.exit("No Cube identity: pass --as <email> or set CUBE_USER_EMAIL.")
    return email


_US_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_GROUPED_INT = re.compile(r"^-?\d{1,3}(,\d{3})+$")


def norm_dim(v) -> str:
    """norm_key, plus the date and number formats Tableau shows."""
    if isinstance(v, str):
        s = v.strip()
        if m := _US_DATE.match(s):
            return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
        if _GROUPED_INT.match(s):
            return s.replace(",", "")
    return norm_key(v)


def table_modified(table: str, client=None) -> dt.datetime | None:
    """When a BigQuery table last changed (UTC)."""
    if client is None:
        from google.cloud import bigquery

        client = bigquery.Client(project=BQ_PROJECT)
    return client.get_table(table).modified


TABLE_CALCS = {"percent_of_total", "running_sum"}


@dataclass(frozen=True)
class Dim:
    cube: str | None
    sql: str
    # Identifies a person: outputs show "a student", or this label, in place of values.
    person: bool | str = False


@dataclass
class Measure:
    caption: str
    cube: str | None
    sql: str | None = None
    num: str | None = None
    den: str | None = None
    scale: float = 1.0
    round: int | None = None
    table_calc: str | None = None
    missing_members: list[str] = field(default_factory=list)
    variants: list[dict] = field(default_factory=list)


@dataclass
class SheetMap:
    name: str
    datasource: str
    dims: dict[str, Dim]
    measures: dict[str, Measure]


def _measure(where: str, caption: str, m: dict, known: set[str]) -> Measure:
    if not m.get("sql") and not (m.get("num") and m.get("den")):
        raise CheckError(f"{where} / {caption}: give sql, or num and den")
    if m.get("table_calc") and m["table_calc"] not in TABLE_CALCS:
        raise CheckError(
            f"{where} / {caption}: table_calc must be one of {sorted(TABLE_CALCS)}"
        )
    missing = list(m.get("missing_members") or [])
    for v in m.get("variants") or []:
        if not v.get("explains"):
            raise CheckError(f"{where} / {caption}: a variant needs explains")
        if not any(v.get(k) for k in ("sql", "num", "where", "cube_filters")):
            raise CheckError(
                f"{where} / {caption}: a variant needs sql, num and den, where, or cube_filters"
            )
        unknown = set(v["explains"]) - known - set(missing)
        if unknown:
            raise CheckError(
                f"{where} / {caption}: variant explains unknown {', '.join(sorted(unknown))}"
            )
    return Measure(
        caption,
        m.get("cube"),
        m.get("sql"),
        m.get("num"),
        m.get("den"),
        float(m.get("scale", 1)),
        m.get("round"),
        m.get("table_calc"),
        missing,
        list(m.get("variants") or []),
    )


def load_checks(path) -> dict:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    for key in ("workbook", "workbook_luid", "student_count", "sheets"):
        if key not in raw:
            raise CheckError(f"{path}: missing '{key}'")
    mismatches = raw.get("mismatches") or {}
    for name, m in mismatches.items():
        for k in ("title", "what", "fix"):
            if k not in m:
                raise CheckError(f"mismatch {name}: missing '{k}'")
        if m["fix"] not in FIX_SIDES:
            raise CheckError(
                f"mismatch {name}: fix must be one of {', '.join(FIX_SIDES)}"
            )
        m.setdefault("labels", [])
        m.setdefault("related", [])
        m.setdefault("where", "tableau")
    sheets = {}
    for name, s in raw["sheets"].items():
        dims = {
            c: Dim(d.get("cube"), d.get("sql") or "", d.get("person", False))
            for c, d in (s.get("dims") or {}).items()
        }
        measures = {
            c: _measure(name, c, m, set(mismatches))
            for c, m in (s.get("measures") or {}).items()
        }
        sheets[name] = SheetMap(name, s.get("datasource", ""), dims, measures)
    members = {m.cube for s in sheets.values() for m in s.measures.values() if m.cube}
    for gid, ms in (raw.get("rows") or {}).items():
        unknown = set(ms) - members
        if unknown:
            raise CheckError(
                f"row {gid}: {', '.join(sorted(unknown))} is not mapped on any sheet"
            )
    return {
        **raw,
        "sheets": sheets,
        "mismatches": mismatches,
        "rows": raw.get("rows") or {},
        "filters": raw.get("filters") or {},
        "param_filters": raw.get("param_filters") or {},
        "cube_filters": raw.get("cube_filters") or [],
        "extract_filters": raw.get("extract_filters") or [],
    }


@dataclass
class Export:
    columns: list[str]
    rows: list[dict[str, str]]


def read_export(data: bytes) -> Export:
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    if not rows:
        return Export([], [])
    seen: dict[str, int] = {}
    cols = []
    for c in rows[0]:
        seen[c] = seen.get(c, 0) + 1
        cols.append(c if seen[c] == 1 else f"{c} ({seen[c]})")
    return Export(cols, [dict(zip(cols, r, strict=False)) for r in rows[1:] if r])


@dataclass(frozen=True)
class Shown:
    value: float
    decimals: int | None  # None: a raw value, compared almost exactly


_SHOWN = re.compile(r"^(-?)(\d{1,3}(?:,\d{3})+|\d*)(?:\.(\d+))?(%?)$")


def parse_shown(s: str | None, round_to: int | None = None) -> Shown | None:
    t = (s or "").strip()
    m = _SHOWN.match(t)
    if not t or not m or not (m.group(2) or m.group(3)):
        return None
    sign, whole, frac, pct = m.group(1), m.group(2), m.group(3) or "", m.group(4)
    value = float(f"{sign}{whole.replace(',', '') or '0'}.{frac or '0'}")
    if pct:
        return Shown(value / 100, len(frac) + 2)
    if "," in whole:
        return Shown(value, len(frac))
    return Shown(value, round_to)


def matches_shown(cube: float | None, shown: Shown | None) -> bool:
    if cube is None or shown is None:
        return cube is None and shown is None
    if shown.decimals is None:
        return abs(cube - shown.value) <= 1e-6 * max(1.0, abs(cube))
    return abs(cube - shown.value) <= 0.5 * 10**-shown.decimals + 1e-9 * max(
        1.0, abs(cube)
    )


def matches_raw(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))


ALL = "(All)"
BLANK = "(Blank)"
TOTAL = "All"  # a total row in a Tableau export
MULTI = "*"  # a mark that covers several values


def _caption_members(checks: dict) -> dict[str, str]:
    out = {
        c: d.cube
        for s in checks["sheets"].values()
        for c, d in s.dims.items()
        if d.cube
    }
    out.update({c: f["cube"] for c, f in checks["filters"].items() if f.get("cube")})
    return out


def state_filters(entry: dict, checks: dict) -> tuple[list[dict], list[str]]:
    st = entry["state"]
    members = _caption_members(checks)
    pairs = list((st.get("filters") or {}).items()) + list(
        (entry.get("click_filters") or {}).items()
    )
    out, missing = [], []
    for caption, value in pairs:
        member = members.get(caption)
        if member is None:
            missing.append(caption)
        elif value == BLANK:
            out.append({"member": member, "operator": "notSet"})
        elif value != ALL:
            out.append({"member": member, "operator": "equals", "values": [str(value)]})
    for caption, value in (st.get("params") or {}).items():
        out += checks["param_filters"].get(caption, {}).get(value, [])
    return out, missing


def hard_filters(checks: dict, datasource: str) -> list[dict]:
    return [
        {k: v for k, v in f.items() if k != "datasource"}
        for f in checks["cube_filters"]
        if f.get("datasource") in (None, datasource)
    ]


def scope_guard(load, checks: dict, extract_counts: dict[str, int]) -> None:
    """Stop when Cube shows no students for a scope value the dashboard has."""
    caption = checks["scope"]["filter"]
    member = _caption_members(checks)[caption]
    rows, _ = load(
        {
            "measures": [checks["student_count"]],
            "dimensions": [member],
            "limit": CUBE_LIMIT,
        }
    )
    cube = {
        norm_dim(r.get(member)): _num(r.get(checks["student_count"])) or 0 for r in rows
    }
    short = sorted(
        v for v, n in extract_counts.items() if n > 0 and not cube.get(norm_dim(v))
    )
    if short:
        raise ScopeError(
            f"Cube shows no students for {caption} {', '.join(short)}, which the dashboard "
            "has: this Cube identity sees less than the dashboard does"
        )


@dataclass
class Cell:
    sheet: str
    state: str
    key: dict[str, str]
    measure: str
    shown: str | None
    tableau: float | None
    cube: float | None
    n_students: int | None
    status: str
    reason: str = ""
    rollups: list[str] = field(default_factory=list)
    verdict: str | None = None
    explained_by: list[str] = field(default_factory=list)
    extract: float | None = None
    variant: float | None = None
    cube_variant: float | None = None


def _int(v) -> int | None:
    n = _num(v)
    return None if n is None else int(n)


def apply_calc(meas: Measure, raw: dict, scale: float) -> dict:
    """Values as the sheet shows them: scaled, or rebuilt as its table calculation."""
    if meas.table_calc == "percent_of_total":
        total = sum(v for v in raw.values() if v is not None)
        return {
            k: (v / total if v is not None and total else None) for k, v in raw.items()
        }
    if meas.table_calc == "running_sum":
        out, run = {}, 0.0
        for k in sorted(raw):
            run += raw[k] or 0.0
            out[k] = run * scale
        return out
    return {k: (None if v is None else v * scale) for k, v in raw.items()}


def compare_export(
    sheet, state_id, export, load, filters, missing, checks
) -> list[Cell]:
    def cell(
        key,
        m,
        shown=None,
        tableau=None,
        cube=None,
        n=None,
        status="mismatch",
        reason="",
        rollups=(),
    ):
        return Cell(
            sheet.name,
            state_id,
            key,
            m,
            shown,
            tableau,
            cube,
            n,
            status,
            reason,
            list(rollups),
        )

    cols = export.columns
    # No header at all: compare at every mapped dimension Cube has, so its rows still show.
    dims = (
        [c for c in cols if c in sheet.dims]
        if cols
        else [d for d in sheet.dims if sheet.dims[d].cube]
    )
    measures = (
        [c for c in cols if c in sheet.measures] if cols else list(sheet.measures)
    )
    cells = [
        cell({}, c, status="not_comparable", reason="unmapped column")
        for c in cols
        if c not in sheet.dims and c not in sheet.measures
    ]
    if missing:
        reason = f"filter {', '.join(missing)} has no Cube member"
        return cells + [
            cell({}, m, status="not_comparable", reason=reason) for m in measures
        ]

    groups: dict[tuple[str, ...], list[dict]] = {}
    for r in export.rows:
        if any(r.get(d) == MULTI for d in dims):
            key = {d: r.get(d, "") for d in dims}
            cells += [
                cell(
                    key, m, r.get(m), status="not_comparable", reason="multi-value mark"
                )
                for m in measures
            ]
            continue
        groups.setdefault(tuple(d for d in dims if r.get(d) == TOTAL), []).append(r)
    if not groups:
        groups[()] = []

    student = checks["student_count"]
    for totals, rows in groups.items():
        grain = [d for d in dims if d not in totals]
        blocked = [d for d in grain if sheet.dims[d].cube is None]
        no_member = [m for m in measures if sheet.measures[m].cube is None]
        if blocked:
            reason = f"dimension {', '.join(blocked)} has no Cube member"
            for r in rows:
                key = {d: r.get(d, "") for d in dims}
                cells += [
                    cell(key, m, r.get(m), status="missing_member", reason=reason)
                    for m in measures
                ]
            continue
        members = sorted(
            {sheet.measures[m].cube for m in measures if sheet.measures[m].cube}
            | {student}
        )
        q = {
            "measures": members,
            "dimensions": [sheet.dims[d].cube for d in grain],
            "filters": filters + hard_filters(checks, sheet.datasource),
            "limit": CUBE_LIMIT,
        }
        cube_rows, rollups = load(q)
        by_key = {
            tuple(norm_dim(cr.get(sheet.dims[d].cube)) for d in grain): cr
            for cr in cube_rows
        }
        values = {
            m: apply_calc(
                sheet.measures[m],
                {k: _num(cr.get(sheet.measures[m].cube)) for k, cr in by_key.items()},
                sheet.measures[m].scale,
            )
            for m in measures
            if m not in no_member
        }
        fixed = {d: TOTAL for d in totals}
        seen = set()
        for r in rows:
            k = tuple(norm_dim(r.get(d)) for d in grain)
            seen.add(k)
            cr = by_key.get(k)
            key = {**{d: r.get(d, "") for d in grain}, **fixed}
            n = _int(cr.get(student)) if cr else None
            for m in measures:
                meas, text = sheet.measures[m], r.get(m)
                shown = parse_shown(text, meas.round)
                if m in no_member:
                    cells.append(
                        cell(
                            key,
                            m,
                            text,
                            status="missing_member",
                            reason="measure has no Cube member",
                        )
                    )
                elif shown is None and (text or "").strip():
                    cells.append(
                        cell(
                            key,
                            m,
                            text,
                            status="not_comparable",
                            reason="value does not parse",
                        )
                    )
                elif cr is None:
                    cells.append(
                        cell(
                            key,
                            m,
                            text,
                            shown and shown.value,
                            None,
                            None,
                            "mismatch",
                            "Tableau shows this slice; Cube does not",
                            rollups,
                        )
                    )
                else:
                    v = values[m].get(k)
                    ok = matches_shown(v, shown)
                    cells.append(
                        cell(
                            key,
                            m,
                            text,
                            shown and shown.value,
                            v,
                            n,
                            "match" if ok else "mismatch",
                            "",
                            rollups,
                        )
                    )
        for k, cr in by_key.items():
            if k in seen:
                continue
            vals = {m: values[m].get(k) for m in values}
            if all(v in (None, 0) for v in vals.values()):
                continue
            key = {**dict(zip(grain, k, strict=True)), **fixed}
            for m, v in vals.items():
                cells.append(
                    cell(
                        key,
                        m,
                        None,
                        None,
                        v,
                        _int(cr.get(student)),
                        "mismatch",
                        "Cube has this slice; Tableau does not",
                        rollups,
                    )
                )
    return cells


def write_cells(path: Path, cells: list[Cell]) -> None:
    Path(path).write_text("".join(json.dumps(asdict(c)) + "\n" for c in cells))


def read_cells(path: Path) -> list[Cell]:
    p = Path(path)
    if not p.exists():
        return []
    return [Cell(**json.loads(line)) for line in p.read_text().splitlines() if line]


SMALL_CELL = 10


def state_status(cells: list[Cell]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in cells:
        if c.status == "mismatch":
            out[c.state] = "mismatch"
        else:
            out.setdefault(c.state, "match")
    return out


def _sql_lit(v) -> str:
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _cond(field_sql: str, value) -> str | None:
    if value == ALL:
        return None
    if value == BLANK:
        return f"{field_sql} is null"
    return f"cast({field_sql} as string) = {_sql_lit(value)}"


def child_values_sql(where, field, student="student_number") -> str:
    conds = [c for f, v in where if (c := _cond(f, v))]
    cond = " and ".join(conds) or "true"
    return (
        # trunk-ignore(bandit/B608): SQL over the dashboard's own extract or rpt_ table; names come from the checks file
        f"select cast({field} as string) as v, count(distinct {student}) as n "
        f"from `{EXTRACT_TABLE}` where {cond} group by 1"
    )


def _sig(st: dict) -> tuple:
    return (
        st["dashboard"],
        tuple(sorted((st.get("filters") or {}).items())),
        tuple(sorted((st.get("params") or {}).items())),
        tuple(sorted((st.get("click") or {}).items())),
    )


def _is_child(k: dict, st: dict) -> bool:
    kf, sf = k.get("filters") or {}, st.get("filters") or {}
    return (
        k["dashboard"] == st["dashboard"]
        and not k.get("params")
        and not k.get("click")
        and len(kf) == len(sf) + 1
        and all(kf.get(c) == v for c, v in sf.items())
    )


def _tree_path(st, trees, fields):
    if st.get("params") or st.get("click") or not st.get("filters"):
        return None
    caps = list(st["filters"])
    if any(c not in fields for c in caps):
        return None
    ds = fields[caps[0]]["datasource"]
    fs = [fields[c]["field"] for c in caps]
    for levels in (trees.get(ds) or {}).values():
        if levels[: len(fs)] == fs:
            return ds, levels
    return None


def _ends_pair(kids):
    if not kids:
        return []
    big = max(kids, key=lambda x: x[1])
    small = min(kids, key=lambda x: x[1])
    return [big] if big == small else [big, small]


def next_states(states, status, trees, cross_cuts, fields, children) -> list[dict]:
    caption_of = {(f["datasource"], f["field"]): c for c, f in fields.items()}
    have = {_sig(e["state"]) for e in states.values()}
    out: list[dict] = []

    def add(st):
        if _sig(st) not in have:
            have.add(_sig(st))
            out.append(st)

    for sid, e in sorted(states.items()):
        st = e["state"]
        path = _tree_path(st, trees, fields)
        if e.get("status") != "ok" or path is None:
            continue
        ds, levels = path
        where = [(fields[c]["field"], v) for c, v in st["filters"].items()]
        bad = status.get(sid) == "mismatch"
        depth = len(st["filters"])
        kids_done = [s for s, k in states.items() if _is_child(k["state"], st)]
        if bad and (
            depth == len(levels)
            or (kids_done and all(status.get(s) != "mismatch" for s in kids_done))
        ):
            for cut in cross_cuts.get(ds, []):
                cap = caption_of.get((ds, cut))
                for v, n in children(ds, where, cut) if cap else []:
                    if v is not None and n >= SMALL_CELL:
                        add(
                            {
                                "dashboard": st["dashboard"],
                                "filters": {**st["filters"], cap: v},
                            }
                        )
        if kids_done or depth >= len(levels):
            continue
        cap = caption_of.get((ds, levels[depth]))
        if not cap:
            continue
        kids = [
            (v, n)
            for v, n in children(ds, where, levels[depth])
            if v is not None and n >= SMALL_CELL
        ]
        for v, _ in kids if bad else _ends_pair(kids):
            add({"dashboard": st["dashboard"], "filters": {**st["filters"], cap: v}})
    return out


def state_where(entry, checks, fields, sheet, public_only=False) -> list[str]:
    st = entry["state"]
    dims_sql = {c: d.sql for c, d in sheet.dims.items()}
    out = []
    pairs = list((st.get("filters") or {}).items()) + list(
        (entry.get("click_filters") or {}).items()
    )
    for caption, value in pairs:
        f = (fields.get(caption) or {}).get("field") or dims_sql.get(caption)
        if f and (c := _cond(f, value)):
            out.append(c)
    for f in checks["extract_filters"]:
        if f.get("datasource") not in (None, sheet.datasource):
            continue
        if public_only and f.get("private"):
            continue
        out.append(f["sql"])
    return out


def extract_sql(sheet, meas, grain, where) -> str:
    sel = [f"{sheet.dims[d].sql} as g{i}" for i, d in enumerate(grain)]
    sel += (
        [f"{meas.sql} as m"]
        if meas.sql
        else [f"{meas.num} as m_num", f"{meas.den} as m_den"]
    )
    # Backticks: sqlglot quotes the name, which to_hyper_sql swaps for the extract table.
    # trunk-ignore(bandit/B608): SQL over the dashboard's own extract or rpt_ table; names come from the checks file
    sql = f"select {', '.join(sel)} from `{EXTRACT_TABLE}`"
    if where:
        sql += " where " + " and ".join(f"({w})" for w in where)
    if grain:
        sql += " group by " + ", ".join(str(i + 1) for i in range(len(grain)))
    return sql


def extract_values(rows, n_grain) -> dict:
    out = {}
    for r in rows:
        k = tuple(norm_dim(r[f"g{i}"]) for i in range(n_grain))
        if "m" in r:
            out[k] = _num(r["m"])
        else:
            num, den = _num(r["m_num"]), _num(r["m_den"])
            out[k] = None if not den else (num or 0.0) / den
    return out


def cell_verdict(c, sides, meas) -> str:
    names = set(c.explained_by)
    if not names:
        return "fail"
    for side, verdict in (
        ("cube", "fix_cube"),
        ("source", "fix_source"),
        ("undecided", "undecided"),
    ):
        if names & sides.get(side, frozenset()):
            return verdict
    if names & set(meas.missing_members):
        return "missing_member"
    return "pass"  # every cause is a dashboard fix: Cube is right


def _grain(c: Cell) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        tuple(d for d, v in c.key.items() if v != TOTAL),
        tuple(d for d, v in c.key.items() if v == TOTAL),
    )


def _key(c: Cell, grain) -> tuple:
    return tuple(norm_dim(c.key[d]) for d in grain)


def _reproduces(value, c: Cell, meas: Measure) -> bool:
    if (c.shown or "").strip():
        return matches_shown(value, parse_shown(c.shown, meas.round))
    return value in (None, 0.0)


def _has_state(st: dict) -> bool:
    return bool(st.get("filters") or st.get("params") or st.get("click"))


def _trust(cells, checks, states, fields, run_extract) -> dict[tuple[str, str], bool]:
    """A measure's SQL is trusted once it reproduces every comparable cell of one state."""
    pools: dict[tuple[str, str], dict[str, list[Cell]]] = {}
    for c in cells:
        if c.status in ("match", "mismatch") and (c.shown or "").strip():
            pools.setdefault((c.sheet, c.measure), {}).setdefault(c.state, []).append(c)
    out = {}
    for (sname, mname), by_state in pools.items():
        defaults = sorted(s for s in by_state if not _has_state(states[s]["state"]))
        state = defaults[0] if defaults else sorted(by_state)[0]
        sheet = checks["sheets"][sname]
        meas = sheet.measures[mname]
        where = state_where(states[state], checks, fields, sheet)
        ok = True
        groups: dict[tuple, list[Cell]] = {}
        for c in by_state[state]:
            groups.setdefault(_grain(c)[0], []).append(c)
        for grain, group in groups.items():
            rows = run_extract(
                sheet.datasource, extract_sql(sheet, meas, list(grain), where)
            )
            ext = apply_calc(meas, extract_values(rows, len(grain)), 1.0)
            ok = ok and all(
                _reproduces(ext.get(_key(c, grain)), c, meas) for c in group
            )
        out[(sname, mname)] = ok
    return out


def _cube_at(load, sheet, meas, grain, filters) -> dict:
    q = {
        "measures": [meas.cube],
        "dimensions": [sheet.dims[d].cube for d in grain],
        "filters": filters,
        "limit": CUBE_LIMIT,
    }
    rows, _ = load(q)
    raw = {
        tuple(norm_dim(r.get(sheet.dims[d].cube)) for d in grain): _num(
            r.get(meas.cube)
        )
        for r in rows
    }
    return apply_calc(meas, raw, meas.scale)


def _variant(v, sheet, meas, grain, where, base, run_extract, load):
    dash = None
    if v.get("where"):
        alt = Measure(
            meas.caption,
            meas.cube,
            table_calc=meas.table_calc,
            sql=_filtered(meas.sql, v["where"]) if meas.sql else None,
            num=None if meas.sql else _filtered(meas.num, v["where"]),
            den=None if meas.sql else _filtered(meas.den, v["where"]),
        )
    elif v.get("sql") or v.get("num"):
        alt = Measure(
            meas.caption,
            meas.cube,
            sql=v.get("sql"),
            num=v.get("num"),
            den=v.get("den"),
            table_calc=meas.table_calc,
        )
    else:
        alt = None
    if alt is not None:
        rows = run_extract(
            sheet.datasource, extract_sql(sheet, alt, list(grain), where)
        )
        dash = apply_calc(alt, extract_values(rows, len(grain)), 1.0)
    cube = (
        _cube_at(load, sheet, meas, grain, base + v["cube_filters"])
        if v.get("cube_filters")
        else None
    )
    return v["explains"], dash, cube


@dataclass
class Live:
    """The live warehouse side of the timing check."""

    rows: Callable[[str, str], list[dict]]  # extract SQL run on the live rpt_ table
    modified: Callable[[str], dt.datetime | None]  # when that table last changed
    cube_refreshed: Callable[[dict], dt.datetime | None]  # Cube's lastRefreshTime


def explain_cells(cells, checks, states, fields, run_extract, load, live=None) -> None:
    sides = fix_sides(checks)
    batches: dict[tuple, list[Cell]] = {}
    for c in cells:
        if c.status == "match":
            c.verdict = "pass"
        elif c.status == "missing_member":
            c.verdict = "missing_member"
        elif c.status == "mismatch":
            batches.setdefault((c.sheet, c.state, _grain(c)[0], c.measure), []).append(
                c
            )
    trusted = _trust(cells, checks, states, fields, run_extract)
    for (sname, state, grain, mname), batch in batches.items():
        sheet = checks["sheets"][sname]
        meas = sheet.measures[mname]
        if not trusted.get((sname, mname)):
            for c in batch:
                c.verdict, c.reason = (
                    "incomplete",
                    "extract SQL does not reproduce Tableau for this measure",
                )
            continue
        entry = states[state]
        where = state_where(entry, checks, fields, sheet)
        base = state_filters(entry, checks)[0] + hard_filters(checks, sheet.datasource)
        rows = run_extract(
            sheet.datasource, extract_sql(sheet, meas, list(grain), where)
        )
        ext = apply_calc(meas, extract_values(rows, len(grain)), 1.0)
        live_v, times = None, (None, None)
        if live is not None:
            lrows = live.rows(
                sheet.datasource, extract_sql(sheet, meas, list(grain), where)
            )
            live_v = apply_calc(meas, extract_values(lrows, len(grain)), 1.0)
            q = {
                "measures": [meas.cube],
                "dimensions": [sheet.dims[d].cube for d in grain],
                "filters": base,
                "limit": CUBE_LIMIT,
            }
            times = (live.cube_refreshed(q), live.modified(sheet.datasource))
        variants = [
            _variant(v, sheet, meas, grain, where, base, run_extract, load)
            for v in meas.variants
        ]
        for c in batch:
            k = _key(c, grain)
            c.extract = ext.get(k)
            if not _reproduces(c.extract, c, meas):
                c.verdict, c.reason = (
                    "incomplete",
                    "extract SQL does not reproduce this cell",
                )
                continue
            if live_v is not None and matches_raw(live_v.get(k), c.cube):
                c.verdict = "pass"
                c.reason = "timing: the extract is older than Cube; Cube matches the live table"
                continue
            for names, dash, cube in variants:
                d_v = c.extract if dash is None else dash.get(k)
                c_v = c.cube if cube is None else cube.get(k)
                if matches_raw(c_v, d_v):
                    c.explained_by, c.variant = list(names), d_v
                    c.cube_variant = None if cube is None else c_v
                    break
            c.verdict = cell_verdict(c, sides, meas)
            cube_at, table_at = times
            if c.verdict == "fail" and cube_at and table_at:
                if cube_at < table_at:
                    c.verdict = "incomplete"
                    c.reason = (
                        f"Cube's data (refreshed {cube_at:%Y-%m-%d %H:%M}) is older than the live "
                        f"table (built {table_at:%Y-%m-%d %H:%M}); re-run explain after Cube refreshes"
                    )
                else:
                    c.reason = (
                        f"Cube refreshed {cube_at:%Y-%m-%d %H:%M}; the live table was built "
                        f"{table_at:%Y-%m-%d %H:%M}"
                    )


ORDER = (
    "fail",
    "incomplete",
    "fix_cube",
    "fix_source",
    "undecided",
    "missing_member",
    "pass",
)


def worst(verdicts) -> str:
    found = [v for v in verdicts if v]
    return min(found, key=ORDER.index) if found else "incomplete"


def _members(checks) -> dict[tuple[str, str], Measure]:
    return {
        (s.name, m.caption): m
        for s in checks["sheets"].values()
        for m in s.measures.values()
    }


def row_results(cells, checks) -> dict[str, dict]:
    by_cell = _members(checks)
    out = {}
    for gid, members in checks["rows"].items():
        mine = [
            c
            for c in cells
            if c.verdict
            and (m := by_cell.get((c.sheet, c.measure)))
            and m.cube in members
        ]
        reopen = sorted(
            {
                mm
                for c in mine
                if c.verdict == "missing_member"
                for mm in by_cell[(c.sheet, c.measure)].missing_members
            }
        )
        out[gid] = {
            "verdict": worst(c.verdict for c in mine),
            "cells": len(mine),
            "by_verdict": dict(Counter(c.verdict for c in mine)),
            "mismatches": sorted({n for c in mine for n in c.explained_by}),
            "reopen_for": reopen,
        }
    return out


def write_latest(path: Path, workbook: str, run_date: str, rows: dict) -> None:
    p = Path(path)
    data = json.loads(p.read_text()) if p.exists() else {}
    for gid, r in rows.items():
        data[gid] = {**r, "dashboard": workbook, "run_date": run_date}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True))


def _issue_labels(t: dict) -> list[str]:
    head = re.match(r"^([a-z]+)", t["title"])
    labels = [head.group(1)] if head else []
    if t["fix"] == "cube":
        labels.append("cube")
    elif t["fix"] == "dashboard":
        labels += {"tableau": ["tableau"], "rpt": ["dbt"]}.get(t["where"], [])
    elif t["fix"] == "source":
        labels.append("data")
    return list(dict.fromkeys([*labels, *t["labels"], "validation"]))


_OTHER_SIDE = "If you think the other side is wrong, say so in a comment."
_ANSWERS = {
    "cube": (
        "Fix the Cube definition to compute what the dashboard shows, then close "
        "this issue; the next validation run checks the fix. " + _OTHER_SIDE
    ),
    "dashboard": (
        "Fix the dashboard (or its model or source) to compute the corrected "
        "formula, then close this issue; the next validation run checks the fix. "
        "Cube already matches the corrected formula. " + _OTHER_SIDE
    ),
    "source": (
        "Fix the source data so Cube and the dashboard both see the corrected "
        "values, then close this issue; the next validation run checks the fix. "
        "Neither side's code changes. " + _OTHER_SIDE
    ),
    "undecided": (
        "Decide which formula is the intended definition. Add the label `fix-cube` "
        "if the dashboard's formula is right and Cube must change, or "
        "`fix-dashboard` if the other formula is right and the dashboard must "
        "change. If you cannot add labels, write a comment that starts with the "
        "word. This issue then becomes the fix ticket for the side you chose."
    ),
}


_SIDE_TITLES = (
    ("cube", "Fix in Cube"),
    ("dashboard", "Fix in the dashboard"),
    ("source", "Fix in the source"),
    ("undecided", "Owner to decide"),
)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _fmt(v) -> str:
    return "nothing" if v is None else f"{v:.4g}"


def masked_key(c: Cell, checks: dict) -> dict[str, str]:
    dims = checks["sheets"][c.sheet].dims if c.sheet in checks["sheets"] else {}
    out = {}
    for d, v in c.key.items():
        p = dims[d].person if d in dims else False
        out[d] = (p if isinstance(p, str) else "a student") if p else v
    return out


def _where_text(c: Cell, checks) -> str:
    key = masked_key(c, checks)
    return ", ".join(f"{d} = {v}" for d, v in key.items()) or "the whole sheet"


def _example(c: Cell, checks, fix: str | None = None) -> str:
    if c.n_students is None or c.n_students < SMALL_CELL:
        return f"{c.sheet}, {_where_text(c, checks)}: small cell"
    text = f"{c.sheet}, {_where_text(c, checks)}: the dashboard shows {c.shown}, Cube gives {_fmt(c.cube)}"
    if fix and c.variant is not None:
        text += f", the other formula gives {_fmt(c.variant)}"
    if c.cube_variant is not None:
        text += f"; Cube without the affected rows gives {_fmt(c.cube_variant)}"
    return text


def _coarsest(cells: list[Cell]) -> list[Cell]:
    return sorted(
        cells,
        key=lambda c: (sum(v != TOTAL for v in c.key.values()), -(c.n_students or 0)),
    )


def coverage_markdown(states, cells) -> str:
    by_status: dict[str, list[str]] = {}
    for sid, e in sorted(states.items()):
        by_status.setdefault(e.get("status", "ok"), []).append(sid)
    lines = ["# Coverage", "", f"States visited: {len(by_status.get('ok', []))}", ""]
    for status in ("filter_ignored", "export_failed"):
        if by_status.get(status):
            lines.append(f"- {status}: {', '.join(by_status[status])}")
    causes = Counter(c.reason for c in cells if c.status == "not_comparable")
    if causes:
        lines += [
            "",
            "Cells not compared:",
            *(f"- {r}: {n}" for r, n in causes.most_common()),
        ]
    return "\n".join(lines) + "\n"


def digest_markdown(workbook, cells, checks) -> str:
    sides = fix_sides(checks)
    lines = [f"# {workbook}: Cube against Tableau", ""]
    lines.append(
        "Verdicts: "
        + ", ".join(
            f"{v} {n}"
            for v, n in Counter(c.verdict for c in cells if c.verdict).most_common()
        )
    )
    for side, title in _SIDE_TITLES:
        slugs = sorted(
            s for s in sides[side] if any(s in c.explained_by for c in cells)
        )
        if not slugs:
            continue
        lines += ["", f"## {title}", ""]
        for s in slugs:
            m = checks["mismatches"][s]
            mine = _coarsest([c for c in cells if s in c.explained_by])
            ref = f"#{m['issue']}" if m.get("issue") else "draft"
            lines.append(f"- **{m['title']}** ({ref}): {m['what']} {len(mine)} cells.")
            lines += [f"  - {_example(c, checks, side)}" for c in mine[:3]]
    fails = _coarsest([c for c in cells if c.verdict == "fail"])
    if fails:
        lines += ["", "## Investigate", ""]
        for (sheet, measure), n in Counter(
            (c.sheet, c.measure) for c in fails
        ).most_common():
            lines.append(f"- {sheet} / {measure}: {n} cells")
        lines += [f"  - {_example(c, checks)}" for c in fails[:5]]
    unsure = Counter(c.reason for c in cells if c.verdict == "incomplete")
    if unsure:
        lines += [
            "",
            "## Could not tell",
            "",
            *(f"- {r}: {n} cells" for r, n in unsure.most_common()),
        ]
    return "\n".join(lines) + "\n"


def issue_drafts(workbook, cells, checks, states, fields) -> dict[str, str]:
    out = {}
    for s, m in checks["mismatches"].items():
        mine = _coarsest([c for c in cells if s in c.explained_by])
        if m.get("issue") or not mine:
            continue
        first = mine[0]
        sheet = checks["sheets"][first.sheet]
        meas = sheet.measures[first.measure]
        grain = list(_grain(first)[0])
        where = state_where(
            states[first.state], checks, fields, sheet, public_only=True
        )
        query = extract_sql(sheet, meas, grain, where)
        alt = [v for v in meas.variants if s in v["explains"]]
        labels = _issue_labels(m)
        related = " ".join(f"#{n}" for n in m.get("related") or [])
        body = [
            f"title: {m['title']}",
            f"labels: {', '.join(labels)}",
            "",
            "## What's happening",
            "",
            m["what"],
            "",
            f"On the {workbook} dashboard, {len(mine)} cells differ between Tableau and Cube "
            "because of this. Examples, coarsest first:",
            "",
            *(f"- {_example(c, checks, m['fix'])}" for c in mine[:5]),
            "",
            "## Steps to reproduce",
            "",
            "1. Run the query below over the dashboard's extract. It gives what Tableau shows.",
            f"2. Query Cube's `{meas.cube}` at the same grain and filters.",
            "3. Compare the two with the other formula below.",
            "",
            "```sql",
            query,
            "```",
            "",
            "The other formula:",
            "",
            "```yaml",
            yaml.safe_dump(alt, sort_keys=False).strip(),
            "```",
            "",
            "## Where",
            "",
            f"- **Code location / dbt project:** {m.get('where', 'tableau')}",
            "- **Environment:** prod",
            f"- **Run, PR, or dashboard link (if any):** {workbook}",
            *([f"- **Related:** {related}"] if related else []),
            "",
            _ANSWERS[m["fix"]],
            "",
            "<details>",
            "<summary>For Claude</summary>",
            "",
            f"> Checks file `.claude/skills/cube-dashboard/checks/{_slug(workbook)}.yml`, "
            f"mismatch `{s}`. Rerun `cube_validate.py explain` after the fix; the cells "
            "above must turn `pass`.",
            "",
            "</details>",
        ]
        out[s] = "\n".join(body) + "\n"
    return out


def write_outputs(out_dir, workbook, run_date, cells, checks, states, fields) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{run_date}-{_slug(workbook)}"
    (out / f"{stem}-coverage.md").write_text(coverage_markdown(states, cells))
    digest = out / f"{stem}-digest.md"
    digest.write_text(digest_markdown(workbook, cells, checks))
    drafts = issue_drafts(workbook, cells, checks, states, fields)
    if drafts:
        (out / f"{stem}-issues").mkdir(exist_ok=True)
        for s, text in drafts.items():
            (out / f"{stem}-issues" / f"{s}.md").write_text(text)
    write_latest(out / "latest.json", workbook, run_date, row_results(cells, checks))
    return digest


SNAPSHOT_ROOT = Path.home() / ".cache" / "cube-validate"


def latest_snapshot(workbook: str, root: Path = SNAPSHOT_ROOT) -> Path:
    base = Path(root) / _slug(workbook)
    dirs = sorted(p for p in base.iterdir() if p.is_dir()) if base.exists() else []
    if not dirs:
        raise FileNotFoundError(
            f"no snapshot for {workbook} under {base}; run the snapshot open step"
        )
    return dirs[-1]


class Extracts:
    """One ExtractSource per datasource, opened on first use."""

    def __init__(self, snapdir: Path, extracts: dict[str, dict]):
        self.snapdir, self.meta, self.open = Path(snapdir), extracts, {}

    def __call__(self, datasource: str, sql: str) -> list[dict]:
        if datasource not in self.open:
            src = ExtractSource(self.snapdir / self.meta[datasource]["file"])
            self.open[datasource] = src.__enter__()
        return self.open[datasource](sql)

    def close(self) -> None:
        for src in self.open.values():
            src.__exit__(None, None, None)
        self.open = {}


def run_compare(checks, snapdir, load, extracts):
    snapdir = Path(snapdir)
    m = json.loads((snapdir / "manifest.json").read_text())
    done = {c.state for c in read_cells(snapdir / "cells.jsonl")}
    cells: list[Cell] = []
    for sid, e in sorted(m["states"].items()):
        if e.get("status") != "ok" or sid in done:
            continue
        filters, missing = state_filters(e, checks)
        for sheet_name, meta in e["sheets"].items():
            sheet = checks["sheets"].get(sheet_name)
            if sheet is None:
                cells.append(
                    Cell(
                        sheet_name,
                        sid,
                        {},
                        "",
                        None,
                        None,
                        None,
                        None,
                        "not_comparable",
                        "unmapped sheet",
                    )
                )
                continue
            export = read_export((snapdir / meta["file"]).read_bytes())
            cells += compare_export(sheet, sid, export, load, filters, missing, checks)
    every = read_cells(snapdir / "cells.jsonl") + cells

    def children(ds, where, f):
        rows = extracts(ds, child_values_sql(where, f))
        return [(r["v"], int(r["n"])) for r in rows]

    nxt = next_states(
        m["states"],
        state_status(every),
        checks.get("trees") or {},
        checks.get("cross_cuts") or {},
        m["fields"],
        children,
    )
    return cells, nxt


def _client() -> CubeClient:
    url = os.environ.get("CUBE_API_URL", DEFAULT_CUBE_URL)
    return CubeClient(url, os.environ["CUBE_API_SECRET"], _user_email(None))


def _live(client: CubeClient) -> Live:
    """Extract SQL on each datasource's live rpt_ table, with both sides' refresh times."""
    built: dict[str, dt.datetime | None] = {}

    def rows(ds, sql):
        return bigquery_rows(sql.replace(EXTRACT_TABLE, live_table(ds)))

    def modified(ds):
        if ds not in built:
            built[ds] = table_modified(live_table(ds))
        return built[ds]

    def cube_refreshed(q):
        client.load(q)
        t = client.last_refresh
        return dt.datetime.fromisoformat(t.replace("Z", "+00:00")) if t else None

    return Live(rows, modified, cube_refreshed)


def _compare(a) -> int:
    checks = load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    m = json.loads((snapdir / "manifest.json").read_text())
    client, extracts = _client(), Extracts(snapdir, m["extracts"])
    try:
        if checks.get("scope"):
            cap = checks["scope"]["filter"]
            f = m["fields"][cap]
            rows = extracts(f["datasource"], child_values_sql([], f["field"]))
            scope_guard(
                client.load,
                checks,
                {r["v"]: int(r["n"]) for r in rows if r["v"] is not None},
            )
        cells, nxt = run_compare(checks, snapdir, client.load, extracts)
    finally:
        extracts.close()
    write_cells(snapdir / "cells.jsonl", read_cells(snapdir / "cells.jsonl") + cells)
    (snapdir / "next_states.yml").write_text(
        yaml.safe_dump(nxt, sort_keys=False, allow_unicode=True)
    )
    counts = Counter(c.status for c in cells)
    print(
        f"compared {len(cells)} cells: "
        + ", ".join(f"{k} {v}" for k, v in counts.most_common())
    )
    print(f"next descent level: {len(nxt)} states -> {snapdir / 'next_states.yml'}")
    return 0


def _explain(a) -> int:
    checks = load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    m = json.loads((snapdir / "manifest.json").read_text())
    cells = read_cells(snapdir / "cells.jsonl")
    client, extracts = _client(), Extracts(snapdir, m["extracts"])
    try:
        explain_cells(
            cells,
            checks,
            m["states"],
            m["fields"],
            extracts,
            client.load,
            _live(client),
        )
    finally:
        extracts.close()
    write_cells(snapdir / "cells.jsonl", cells)
    counts = Counter(c.verdict for c in cells if c.verdict)
    print("verdicts: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()))
    return 0


def _drafts(a) -> int:
    checks = load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    m = json.loads((snapdir / "manifest.json").read_text())
    cells = read_cells(snapdir / "cells.jsonl")
    digest = write_outputs(
        Path(a.out),
        checks["workbook"],
        dt.date.today().isoformat(),
        cells,
        checks,
        m["states"],
        m["fields"],
    )
    print(f"digest: {digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cube_validate")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("compare", "explain"):
        sub.add_parser(name).add_argument("checks")
    d = sub.add_parser("drafts")
    d.add_argument("checks")
    d.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    return {"compare": _compare, "explain": _explain, "drafts": _drafts}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
