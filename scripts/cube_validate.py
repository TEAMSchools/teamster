"""The Cube side of Cube validation: compare, explain, report.

    uv run --with tableauhyperapi scripts/cube_validate.py compare <checks.yml>
    uv run --with tableauhyperapi scripts/cube_validate.py explain <checks.yml>
    uv run --with tableauhyperapi scripts/cube_validate.py drafts <checks.yml>
    uv run --with tableauhyperapi scripts/cube_validate.py map <checks.yml>

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
import statistics
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


FIX_SIDES = ("cube", "dashboard", "source", "undecided", "accepted")

# Name columns. Same words as cube_validate_snapshot.PERSON_FIELD: a dimension or
# filter reading one must say who it names (person:), so outputs show a label.
PERSON_WORDS = ("lastfirst", "student_name", "first_name", "last_name", "teacher_name")
PERSON_SQL = re.compile(rf"({'|'.join(PERSON_WORDS)})\b")


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


ROUTES = "cube-routes-disagree"
ROUTES_MISMATCH = {
    "title": "fix(cube): a rollup and the fact table answer the same query differently",
    "what": (
        "Cube gives one number when the measure is asked alone, as people ask "
        "(often served by a rollup), and another when the student count is asked "
        "with it (read from the fact table)."
    ),
    "fix": "cube",
}


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

    def meta(self) -> list[str]:
        """Every member name this identity can see, for drafting a mapping."""
        r = self._http().get(
            f"{self.url}/meta", headers={"Authorization": self._token()}
        )
        body = r.json()
        return sorted(
            x["name"]
            for c in body.get("cubes", [])
            for kind in ("measures", "dimensions")
            for x in c.get(kind, [])
        )


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
    """norm_key, plus the date and number formats Tableau shows and its blanks."""
    if v is None or (isinstance(v, str) and v.strip() in ("", "Null")):
        return norm_key(None)
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
    # One Cube member, several (joined with " - " to match `sql`), or none.
    cube: str | tuple[str, ...] | None
    sql: str
    # Identifies a person: outputs show "a student", or this label, in place of values.
    person: bool | str = False
    # Regexes tried in order; the first that matches gives, in its one group, the
    # join key inside the displayed text (Tableau shows a section as
    # "G5 - <teacher> - 501"; the key is 501).
    keys: tuple[str, ...] = ()
    # Tableau aliases to stored values ("K" for grade 0), applied after the key.
    values: dict | None = None
    # Set when `cube` is a time dimension, asked at this granularity ("week").
    granularity: str | None = None
    # A known attribute of a coarser mark: never part of the grain (the `*` rule
    # stays the fallback for ones not listed).
    attr: bool = False


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
    cube_filters: list[dict] = field(
        default_factory=list
    )  # Cube filters for this measure alone
    where: str | None = None  # an extract condition for this measure alone
    diff: tuple[str, str] | None = None  # A minus B, two plain measures on the sheet


@dataclass
class SheetMap:
    name: str
    datasource: str
    dims: dict[str, Dim]
    measures: dict[str, Measure]
    cube_filters: list[dict] = field(default_factory=list)
    extract_filters: list[dict] = field(default_factory=list)


def _measure(where: str, caption: str, m: dict, known: set[str]) -> Measure:
    if not m.get("sql") and not (m.get("num") and m.get("den")) and not m.get("diff"):
        raise CheckError(f"{where} / {caption}: give sql, num and den, or diff")
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
        list(m.get("cube_filters") or []),
        m.get("where"),
        tuple(m["diff"]) if m.get("diff") else None,
    )


def _dim_keys(d: dict) -> tuple[str, ...]:
    """A dimension's key patterns: `keys:`, or a single `key:`."""
    return tuple(d.get("keys") or ([d["key"]] if d.get("key") else []))


def load_checks(path) -> dict:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    for key in ("workbook", "workbook_luid", "student_count", "sheets"):
        if key not in raw:
            raise CheckError(f"{path}: missing '{key}'")
    mismatches = raw.get("mismatches") or {}
    # Built in: the checks file may add issue:, labels: or related: to it.
    mismatches[ROUTES] = {**ROUTES_MISMATCH, **(mismatches.get(ROUTES) or {})}
    for name, m in mismatches.items():
        for k in ("title", "what", "fix"):
            if k not in m:
                raise CheckError(f"mismatch {name}: missing '{k}'")
        if m["fix"] not in FIX_SIDES:
            raise CheckError(
                f"mismatch {name}: fix must be one of {', '.join(FIX_SIDES)}"
            )
        if m["fix"] == "accepted" and not m.get("issue"):
            raise CheckError(f"mismatch {name}: fix accepted needs issue: (the ruling)")
        m.setdefault("labels", [])
        m.setdefault("related", [])
        m.setdefault("where", "tableau")
    sheets = {}
    for name, s in raw["sheets"].items():
        dims = {}
        for c, d in (s.get("dims") or {}).items():
            cube = d.get("cube")
            granularity = None
            if isinstance(cube, dict):
                cube, granularity = cube["time"], cube["granularity"]
            dims[c] = Dim(
                tuple(cube) if isinstance(cube, list) else cube,
                d.get("sql") or "",
                d.get("person", False),
                _dim_keys(d),
                {str(k): str(v) for k, v in (d.get("values") or {}).items()} or None,
                granularity=granularity,
                attr=bool(d.get("attr")),
            )
        measures = {
            c: _measure(name, c, m, set(mismatches))
            for c, m in (s.get("measures") or {}).items()
        }
        for c, meas in measures.items():
            if not meas.diff:
                continue
            parts = [measures.get(x) for x in meas.diff]
            if len(meas.diff) != 2 or any(p is None or p.diff for p in parts):
                raise CheckError(
                    f"{name} / {c}: diff names 2 plain measures on this sheet"
                )
            if meas.variants:
                raise CheckError(f"{name} / {c}: a diff measure takes no variants")
        sheets[name] = SheetMap(
            name,
            s.get("datasource", ""),
            dims,
            measures,
            list(s.get("cube_filters") or []),
            list(s.get("extract_filters") or []),
        )
    for name, s in raw["sheets"].items():
        for c, d in (s.get("dims") or {}).items():
            for pattern in _dim_keys(d):
                try:
                    groups = re.compile(pattern).groups
                except re.error:
                    groups = 0
                if groups != 1:
                    raise CheckError(
                        f"{name} / {c}: key needs one capture group around the join key"
                    )
            if PERSON_SQL.search(d.get("sql") or "") and not d.get("person"):
                raise CheckError(
                    f"{name} / {c}: its sql reads a name column; add person: "
                    "(true for a student, or a label such as 'a teacher')"
                )
    for c, f in (raw.get("filters") or {}).items():
        if PERSON_SQL.search(f.get("sql") or "") and not f.get("person"):
            raise CheckError(f"filter {c}: its sql reads a name column; add person:")
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
        "param_where": raw.get("param_where") or {},
        "ignore_sheet_filters": raw.get("ignore_sheet_filters") or [],
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
    out = Export(cols, [dict(zip(cols, r, strict=False)) for r in rows[1:] if r])
    return _pivot_measure_names(out) if MEASURE_NAMES in cols else out


MEASURE_NAMES, MEASURE_VALUES = "Measure Names", "Measure Values"


def _pivot_measure_names(e: Export) -> Export:
    """A sheet with Measure Names exports one row per measure; make it one column
    per measure, so it compares like any other sheet."""
    dims = [c for c in e.columns if c not in (MEASURE_NAMES, MEASURE_VALUES)]
    measures = list(dict.fromkeys(r[MEASURE_NAMES] for r in e.rows))
    wide: dict[tuple, dict[str, str]] = {}
    for r in e.rows:
        key = tuple(r.get(d, "") for d in dims)
        wide.setdefault(key, dict(zip(dims, key, strict=True)))[r[MEASURE_NAMES]] = (
            r.get(MEASURE_VALUES, "")
        )
    return Export(dims + measures, list(wide.values()))


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


def matches_cell(
    value: float | None, text: str | None, round_to: int | None = None
) -> bool:
    """A Cube or extract value against a Tableau cell. A blank cell matches a null
    or 0: Tableau leaves both empty."""
    if not (text or "").strip():
        return value in (None, 0.0)
    return matches_shown(value, parse_shown(text, round_to))


def matches_raw(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))


ALL = "(All)"
BLANK = "(Blank)"
TOTAL = "All"  # a total row in a Tableau export
MULTI = "*"  # a mark that covers several values


@dataclass
class Lists:
    """What (All) and a group bin stand for, as the snapshot recorded them."""

    all_values: dict[str, list[str]] = field(default_factory=dict)
    groups: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def of(cls, manifest: dict) -> Lists:
        return cls(manifest.get("all_values") or {}, manifest.get("groups") or {})

    def expand(self, caption: str, value):
        """A filter value as the stored values it stands for: a group's bins become
        their members. None: an (All) the snapshot has no list for."""
        g = self.groups.get(caption)
        if g is not None:
            bins = g["bins"]
            if value == ALL:
                return [v for members in bins.values() for v in members]
            names = value if isinstance(value, list) else [value]
            return [v for n in names for v in bins.get(n, [])]
        if value == ALL:
            found = self.all_values.get(caption)
            return None if found is None else list(found)
        return value

    def column(self, caption: str) -> str | None:
        """A group caption's underlying extract column."""
        g = self.groups.get(caption)
        return g["field"] if g is not None else None


def _caption_members(checks: dict) -> dict[str, str]:
    out = {
        c: d.cube
        for s in checks["sheets"].values()
        for c, d in s.dims.items()
        # A time dimension's caption would filter through a date range; none does yet.
        if isinstance(d.cube, str) and not d.granularity
    }
    out.update({c: f["cube"] for c, f in checks["filters"].items() if f.get("cube")})
    return out


def _person_captions(checks: dict) -> dict[str, str]:
    """Captions that identify a person, with the label shown in their place."""
    out = {}
    for s in checks["sheets"].values():
        for c, d in s.dims.items():
            if d.person:
                out[c] = d.person if isinstance(d.person, str) else "a student"
    for c, f in checks["filters"].items():
        if f.get("person"):
            out[c] = f["person"] if isinstance(f["person"], str) else "a student"
    return out


def _own_filters(
    entry: dict,
    defaults: dict | None,
    lists: Lists | None = None,
    keyed: dict[str, Dim] | None = None,
) -> list[tuple[str, object]]:
    """A state's filters as Tableau applies them: saved defaults it keeps, its own
    filters, and its click (with Tableau's formatting removed), each expanded to
    the stored values it stands for."""
    lists = lists or Lists()
    st = entry["state"]
    own = dict(st.get("filters") or {})
    keyed = keyed or {}

    def click_value(c, v):
        # A label the pattern misses has no safe value: None reports the filter
        # missing rather than sending a raw label (a name) to Cube or a draft.
        if c in keyed:
            v = _key_text(keyed[c], v)
            return v and norm_dim(v)
        return norm_dim(v)

    clicks = {
        c: click_value(c, v) for c, v in (entry.get("click_filters") or {}).items()
    }
    kept = [
        (c, list(v))
        for c, v in (defaults or {}).items()
        if c not in own and c not in clicks
    ]
    return [(c, lists.expand(c, v)) for c, v in [*kept, *own.items(), *clicks.items()]]


def state_filters(
    entry: dict, checks: dict, defaults: dict | None = None, lists: Lists | None = None
) -> tuple[list[dict], list[str]]:
    st = entry["state"]
    members = _caption_members(checks)
    out, missing = [], []
    for caption, value in _own_filters(entry, defaults, lists, _keyed_dims(checks)):
        member = members.get(caption)
        if value is None:
            missing.append(caption)
            continue
        # A lookup from the extract's value to Cube's (school id to abbreviation).
        lookup = (checks["filters"].get(caption) or {}).get("values")
        if lookup is not None and value != BLANK:
            wanted = value if isinstance(value, list) else [value]
            found = [lookup.get(str(v)) for v in wanted]
            if None in found:
                missing.append(caption)
                continue
            value = found if isinstance(value, list) else found[0]
        if member is None or value == []:
            missing.append(caption)
        elif isinstance(value, list):
            out.append(
                {
                    "member": member,
                    "operator": "equals",
                    "values": [str(v) for v in value],
                }
            )
        elif value == BLANK:
            out.append({"member": member, "operator": "notSet"})
        else:
            out.append({"member": member, "operator": "equals", "values": [str(value)]})
    for caption, value in (st.get("params") or {}).items():
        out += checks["param_filters"].get(caption, {}).get(value, [])
    return out, missing


NULL_MEMBER = "%null%"  # how Tableau saves a blank member


def sheet_conditions(
    entries, entry, checks, public_only=False
) -> tuple[list[str], list[dict], list[str]]:
    """A sheet's saved filters as extract conditions and Cube filters, for those the
    state keeps: a state's own filter on a caption replaces the saved one. Also
    returns the captions Cube cannot express, unless ignore_sheet_filters names them.
    With public_only, a person caption's values become its label."""
    st = entry["state"]
    people = _person_captions(checks) if public_only else {}
    own = set(st.get("filters") or {}) | set(entry.get("click_filters") or {})
    ignored = set(checks.get("ignore_sheet_filters") or [])
    members = _caption_members(checks)
    where: list[str] = []
    cube: list[dict] = []
    missing: list[str] = []
    for f in entries or []:
        cap = f["caption"]
        if cap in own or cap in ignored:
            continue
        col, numeric = f["field"], bool(f.get("numeric"))
        vals = [v for v in f.get("values") or [] if v != NULL_MEMBER]
        if cap in people and vals:
            vals = [people[cap]]
        # Tableau saves whole numbers as "1.0"; the extract may print "1".
        texts = [x for v in vals for x in dict.fromkeys([v, norm_key(v)])]
        has_null = NULL_MEMBER in (f.get("values") or [])
        lhs = col if numeric else f"cast({col} as string)"
        listed = ", ".join(
            v if numeric else _sql_lit(v) for v in (vals if numeric else texts)
        )
        if not f.get("calculated"):
            if f["op"] == "range":
                if f.get("low") is not None:
                    where.append(f"{col} >= {f['low']}")
                if f.get("high") is not None:
                    where.append(f"{col} <= {f['high']}")
            elif f["op"] == "in":
                cond = f"{lhs} in ({listed})" if vals else ""
                if has_null:
                    cond = f"({cond} or {col} is null)" if cond else f"{col} is null"
                if cond:
                    where.append(cond)
            else:
                parts = [f"{col} is not null"] if has_null else []
                if vals:
                    parts.append(
                        f"{lhs} not in ({listed})"
                        if has_null
                        else f"({col} is null or {lhs} not in ({listed}))"
                    )
                where.append(" and ".join(parts))
        member = members.get(cap)
        lookup = (checks["filters"].get(cap) or {}).get("values")
        if cap in people:
            lookup = None
        mapped = [lookup.get(v) for v in vals] if lookup is not None else list(vals)
        if member is None or None in mapped:
            missing.append(cap)
            continue
        mapped = list(dict.fromkeys(norm_key(v) for v in mapped))
        if f["op"] == "range":
            if f.get("low") is not None:
                cube.append(
                    {"member": member, "operator": "gte", "values": [str(f["low"])]}
                )
            if f.get("high") is not None:
                cube.append(
                    {"member": member, "operator": "lte", "values": [str(f["high"])]}
                )
        elif f["op"] == "in":
            eq = {"member": member, "operator": "equals", "values": mapped}
            unset = {"member": member, "operator": "notSet"}
            if mapped and has_null:
                cube.append({"or": [eq, unset]})
            else:
                cube.append(eq if mapped else unset)
        else:
            if has_null:
                cube.append({"member": member, "operator": "set"})
            if mapped:
                cube.append(
                    {"member": member, "operator": "notEquals", "values": mapped}
                )
    return where, cube, missing


def sheet_defaults(defaults: dict | None, saved) -> dict | None:
    """The dashboard's saved defaults a sheet keeps: a sheet that saves its own
    filter on a caption replaces the dashboard default (a group's default is its
    bin name, while the sheet's saved filter lists the bin's members)."""
    if not defaults:
        return defaults
    covered = {f["caption"] for f in saved or []}
    return {c: v for c, v in defaults.items() if c not in covered}


def hard_filters(
    checks: dict, sheet: SheetMap, public_only: bool = False
) -> list[dict]:
    """The dashboard's hard Cube filters for one sheet: the datasource's, then the
    sheet's own. Only Cube's keys are sent."""
    every = [
        f
        for f in checks["cube_filters"]
        if f.get("datasource") in (None, sheet.datasource)
    ] + list(sheet.cube_filters)
    return [
        {k: v for k, v in f.items() if k not in ("datasource", "private")}
        for f in every
        if not (public_only and f.get("private"))
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
    why: str = ""  # explain's reason for the verdict
    cube_alone: float | None = None  # Cube's value when the measure is asked alone
    rollups_alone: list[str] = field(default_factory=list)
    routes: bool = False  # Cube's two routes disagree at the shown precision
    reproduces: bool | None = None  # the extract SQL gives Tableau's value
    live: float | None = None  # the same SQL on the live rpt_ table
    live_students: int | None = None
    cube_students: int | None = None
    gap: str = ""  # "row gap" (student counts differ) or "formula gap"


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


@dataclass
class Answer:
    """Cube's raw values for one measure at one grain, by both routes."""

    fact: dict[tuple, float | None]  # asked with the student count
    alone: dict[tuple, float | None]  # the measure alone, as people ask
    students: dict[tuple, int | None]
    rollups: list[str]
    rollups_alone: list[str]


def cube_query(sheet, grain, measures, filters) -> dict:
    q = {
        "measures": sorted({m for m in measures if m}),
        "dimensions": [
            m
            for d in grain
            if not sheet.dims[d].granularity
            for m in cube_members(sheet.dims[d])
        ],
        "filters": filters,
        "limit": CUBE_LIMIT,
    }
    times = [
        {"dimension": sheet.dims[d].cube, "granularity": sheet.dims[d].granularity}
        for d in grain
        if sheet.dims[d].granularity
    ]
    if times:
        q["timeDimensions"] = times
    return q


def cube_members(dim: Dim) -> list[str]:
    if dim.cube is None:
        return []
    return list(dim.cube) if isinstance(dim.cube, tuple) else [dim.cube]


def cube_key(row: dict, dim: Dim) -> str:
    """A Cube row's value for a dimension: a time dimension at its granularity, or
    several members joined with " - ", as the extract expression does."""
    if dim.granularity:
        return norm_dim(row.get(f"{dim.cube}.{dim.granularity}"))
    ms = cube_members(dim)
    if len(ms) == 1:
        return norm_dim(row.get(ms[0]))
    return " - ".join(norm_dim(row.get(m)) for m in ms)


def _multi(sheet, grain) -> list[int]:
    return [i for i, d in enumerate(grain) if len(cube_members(sheet.dims[d])) > 1]


class Keys:
    """Row keys at a grain, joinable by a Tableau key: exactly, or, where a
    multi-member dimension shows only its last member (an ES/MS section label
    has no course), by the keys that end with it."""

    def __init__(self, keys, multi: list[int]):
        self.all, self.multi = set(keys), multi
        self.short: dict[tuple, list[tuple]] = {}
        for h in self.all if multi else ():
            self.short.setdefault(self._short(h), []).append(h)

    def _short(self, h: tuple) -> tuple:
        return tuple(
            v.rsplit(" - ", 1)[-1] if i in self.multi else v for i, v in enumerate(h)
        )

    def find(self, k: tuple) -> list[tuple]:
        if k in self.all:
            return [k]
        return sorted(self.short.get(k, []))


def _by_key(rows, sheet, grain) -> dict[tuple, dict]:
    return {tuple(cube_key(r, sheet.dims[d]) for d in grain): r for r in rows}


def _minus(a: dict, b: dict) -> dict:
    return {
        k: None if a.get(k) is None or b.get(k) is None else a[k] - b[k]
        for k in a.keys() | b.keys()
    }


def _has_cube(sheet, meas) -> bool:
    if meas.diff:
        return all(sheet.measures[x].cube for x in meas.diff)
    return meas.cube is not None


def _ask_cube(sheet, grain, wanted, load, filters, student) -> dict[str, Answer]:
    """Each measure's raw values at the grain by both of Cube's routes: with the
    student count (read from the fact) and alone (often served by a rollup). One
    pair of queries per distinct set of measure filters. A difference is built
    from the answers for its two parts."""
    measures = list(
        dict.fromkeys(x for m in wanted for x in (sheet.measures[m].diff or (m,)))
    )
    by_filters: dict[str, list[str]] = {}
    for m in measures:
        key = json.dumps(sheet.measures[m].cube_filters, sort_keys=True)
        by_filters.setdefault(key, []).append(m)
    out: dict[str, Answer] = {}
    for key, ms in by_filters.items():
        f = filters + json.loads(key)
        members = [sheet.measures[m].cube for m in ms]
        rows, rollups = load(cube_query(sheet, grain, [*members, student], f))
        alone_rows, rollups_alone = load(cube_query(sheet, grain, members, f))
        fact, alone = _by_key(rows, sheet, grain), _by_key(alone_rows, sheet, grain)
        for m in ms:
            cube = sheet.measures[m].cube
            out[m] = Answer(
                {k: _num(r.get(cube)) for k, r in fact.items()},
                {k: _num(r.get(cube)) for k, r in alone.items()},
                {k: _int(r.get(student)) for k, r in fact.items()},
                list(rollups),
                list(rollups_alone),
            )
    for m in wanted:
        d = sheet.measures[m].diff
        if d:
            a, b = out[d[0]], out[d[1]]
            out[m] = Answer(
                _minus(a.fact, b.fact),
                _minus(a.alone, b.alone),
                a.students,
                sorted({*a.rollups, *b.rollups}),
                sorted({*a.rollups_alone, *b.rollups_alone}),
            )
    return {m: out[m] for m in wanted}


def _bins(sheet, grain, lists) -> tuple[int, list[str], list[tuple[str, dict]]] | None:
    """A grain's first group dimension, split for one query per bin: its position,
    the grain without it, and each non-empty bin with a filter to its members.
    None when the grain holds no group. Compare and explain both ask through this,
    since counts and rates do not add up across members."""
    i = next((i for i, d in enumerate(grain) if d in lists.groups), None)
    if i is None:
        return None
    d = grain[i]
    each = [
        (
            b,
            {
                "member": sheet.dims[d].cube,
                "operator": "equals",
                "values": [str(v) for v in members],
            },
        )
        for b, members in lists.groups[d]["bins"].items()
        if members
    ]
    return i, [*grain[:i], *grain[i + 1 :]], each


def _rekey(values: dict, i: int, b: str) -> dict:
    """One bin's answers keyed at the full grain: the bin name back at position i."""
    return {(*k[:i], norm_dim(b), *k[i:]): v for k, v in values.items()}


def _ask_by_bin(
    sheet, grain, measures, load, filters, student, lists
) -> dict[str, Answer]:
    """Answers at a grain holding a group dimension: one set of queries per bin.
    Raw values: the caller rebuilds table calculations after the bins merge."""
    split = _bins(sheet, grain, lists)
    if split is None:
        return _ask_cube(sheet, grain, measures, load, filters, student)
    i, rest, each = split
    out: dict[str, Answer] = {}
    for b, only in each:
        part = _ask_by_bin(
            sheet, rest, measures, load, [*filters, only], student, lists
        )
        for m, a in part.items():
            o = out.setdefault(m, Answer({}, {}, {}, [], []))
            o.fact.update(_rekey(a.fact, i, b))
            o.alone.update(_rekey(a.alone, i, b))
            o.students.update(_rekey(a.students, i, b))
            o.rollups = sorted({*o.rollups, *a.rollups})
            o.rollups_alone = sorted({*o.rollups_alone, *a.rollups_alone})
    return out


def _dim_sql(sheet, d, lists=None) -> str:
    """A dimension's extract SQL; a group becomes a CASE over its bins' members."""
    sql = sheet.dims[d].sql
    g = (lists.groups if lists else {}).get(d)
    if not g:
        return sql
    whens = " ".join(
        f"when cast({sql} as string) in ({', '.join(_sql_lit(v) for v in members)}) "
        f"then {_sql_lit(b)}"
        for b, members in g["bins"].items()
        if members
    )
    return f"case {whens} end"


def routes_agree(fact, alone, shown: Shown | None) -> bool:
    """Whether Cube's two routes give the same number at the precision Tableau shows."""
    if fact is None or alone is None:
        return (fact or 0.0) == (alone or 0.0)
    if matches_raw(fact, alone):
        return True
    if shown is None or shown.decimals is None:
        return False
    return round(fact, shown.decimals) == round(alone, shown.decimals)


def compare_export(
    sheet, state_id, export, load, filters, missing, checks, lists=None
) -> list[Cell]:
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
        Cell(
            sheet.name,
            state_id,
            {},
            c,
            None,
            None,
            None,
            None,
            "not_comparable",
            "unmapped column",
        )
        for c in cols
        if c not in sheet.dims and c not in sheet.measures
    ]
    if missing:
        # Cube cannot express a filter the dashboard applies: a missing member.
        reason = f"filter {', '.join(missing)} has no Cube member"
        return cells + [
            Cell(
                sheet.name,
                state_id,
                {},
                m,
                None,
                None,
                None,
                None,
                "missing_member",
                reason,
            )
            for m in measures
        ]

    # A dimension showing "*" is an attribute (ATTR) of a coarser mark, never part
    # of the mark's grain: leave it out, and compare at the remaining dimensions.
    attrs = [
        d
        for d in dims
        if sheet.dims[d].attr or any(r.get(d) == MULTI for r in export.rows)
    ]
    dims = [d for d in dims if d not in attrs]
    groups: dict[tuple[str, ...], list[dict]] = {}
    for r in export.rows:
        groups.setdefault(tuple(d for d in dims if r.get(d) == TOTAL), []).append(r)
    if not groups:
        groups[()] = []
    every = filters + hard_filters(checks, sheet)
    for totals, rows in groups.items():
        grain = [d for d in dims if d not in totals]
        cells += _compare_grain(
            sheet,
            state_id,
            grain,
            totals,
            rows,
            dims,
            measures,
            load,
            every,
            checks["student_count"],
            lists,
        )
    return cells


def _compare_grain(
    sheet,
    state_id,
    grain,
    totals,
    rows,
    dims,
    measures,
    load,
    filters,
    student,
    lists=None,
) -> list[Cell]:
    """One grain's cells: each Tableau row against Cube, then Cube's extra slices."""

    def cell(
        key, m, status, reason="", shown=None, tableau=None, cube=None, n=None, **kw
    ):
        return Cell(
            sheet.name, state_id, key, m, shown, tableau, cube, n, status, reason, **kw
        )

    blocked = [d for d in grain if sheet.dims[d].cube is None]
    if blocked:
        reason = f"dimension {', '.join(blocked)} has no Cube member"
        return [
            cell(
                {d: r.get(d, "") for d in dims},
                m,
                "missing_member",
                reason,
                shown=r.get(m),
            )
            for r in rows
            for m in measures
        ]
    asked = [m for m in measures if _has_cube(sheet, sheet.measures[m])]
    raw = _ask_by_bin(sheet, grain, asked, load, filters, student, lists or Lists())
    answers = {
        m: Answer(
            apply_calc(sheet.measures[m], a.fact, sheet.measures[m].scale),
            apply_calc(sheet.measures[m], a.alone, sheet.measures[m].scale),
            a.students,
            a.rollups,
            a.rollups_alone,
        )
        for m, a in raw.items()
    }
    index = Keys({k for a in answers.values() for k in a.fact}, _multi(sheet, grain))
    fixed = {d: TOTAL for d in totals}
    out, seen = [], set()
    for r in rows:
        # Every candidate counts as seen: an ambiguous key is reported once, here.
        hits = index.find(tuple(tableau_key(sheet, d, r.get(d)) for d in grain))
        seen.update(hits)
        k = hits[0] if len(hits) == 1 else None
        key = {**{d: r.get(d, "") for d in grain}, **fixed}
        for m in measures:
            meas, text = sheet.measures[m], r.get(m)
            shown = parse_shown(text, meas.round)
            a = answers.get(m)
            if a is None:
                out.append(
                    cell(
                        key,
                        m,
                        "missing_member",
                        "measure has no Cube member",
                        shown=text,
                    )
                )
            elif shown is None and (text or "").strip():
                out.append(
                    cell(
                        key,
                        m,
                        "not_comparable",
                        "value does not parse",
                        shown=text,
                    )
                )
            elif len(hits) > 1:
                out.append(
                    cell(
                        key,
                        m,
                        "not_comparable",
                        "the shown key matches several Cube rows",
                        shown=text,
                    )
                )
            elif k is None or k not in a.fact:
                out.append(
                    cell(
                        key,
                        m,
                        "mismatch",
                        "Tableau shows this slice; Cube does not",
                        shown=text,
                        tableau=shown and shown.value,
                        rollups=a.rollups,
                        rollups_alone=a.rollups_alone,
                    )
                )
            else:
                v, alone = a.fact.get(k), a.alone.get(k)
                split = not routes_agree(v, alone, shown)
                ok = not split and matches_cell(v, text, meas.round)
                reason = (
                    f"Cube's routes disagree: alone {_fmt(alone)}, with the student "
                    f"count {_fmt(v)}"
                    if split
                    else ""
                )
                out.append(
                    cell(
                        key,
                        m,
                        "match" if ok else "mismatch",
                        reason,
                        shown=text,
                        tableau=shown and shown.value,
                        cube=v,
                        n=a.students.get(k),
                        rollups=a.rollups,
                        rollups_alone=a.rollups_alone,
                        cube_alone=alone,
                        routes=split,
                    )
                )
    for k in sorted({k for a in answers.values() for k in a.fact} - seen):
        vals = {m: a.fact.get(k) for m, a in answers.items()}
        if all(v in (None, 0) for v in vals.values()):
            continue
        key = {**dict(zip(grain, k, strict=True)), **fixed}
        for m, v in vals.items():
            a = answers[m]
            out.append(
                cell(
                    key,
                    m,
                    "mismatch",
                    "Cube has this slice; Tableau does not",
                    cube=v,
                    n=a.students.get(k),
                    rollups=a.rollups,
                    rollups_alone=a.rollups_alone,
                )
            )
    return out


def write_cells(path: Path, cells: list[Cell]) -> None:
    Path(path).write_text("".join(json.dumps(asdict(c)) + "\n" for c in cells))


def read_cells(path: Path) -> list[Cell]:
    p = Path(path)
    if not p.exists():
        return []
    return [Cell(**json.loads(line)) for line in p.read_text().splitlines() if line]


SMALL_CELL = 10
TRUST = 0.95


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
    # The manifest stores filters with sorted keys, so match the levels as a set.
    fs = {fields[c]["field"] for c in caps}
    for levels in (trees.get(ds) or {}).values():
        if set(levels[: len(fs)]) == fs:
            return ds, levels
    return None


def _ends_pair(kids):
    if not kids:
        return []
    big = max(kids, key=lambda x: x[1])
    small = min(kids, key=lambda x: x[1])
    return [big] if big == small else [big, small]


def next_states(
    states, status, trees, cross_cuts, fields, children, members: set[str] | None = None
) -> list[dict]:
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
        # The descent stops at the last level with a Cube member: a deeper state
        # could only end missing_member.
        if members is not None:
            usable = []
            for f in levels:
                if caption_of.get((ds, f)) not in members:
                    break
                usable.append(f)
            levels = usable or levels[:1]
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
    # A cross-cut exports its largest value first; when that mismatches, its other
    # values are proposed, to see whether the gap follows the flag.
    for sid, e in sorted(states.items()):
        st = e["state"]
        fs = st.get("filters") or {}
        if (
            e.get("status") != "ok"
            or status.get(sid) != "mismatch"
            or st.get("params")
            or st.get("click")
            or len(fs) != 1
        ):
            continue
        ((cap, _),) = fs.items()
        f = fields.get(cap)
        if not f or f["field"] not in cross_cuts.get(f["datasource"], []):
            continue
        for v, n in children(f["datasource"], [], f["field"]):
            if v is not None and n >= SMALL_CELL:
                add({"dashboard": st["dashboard"], "filters": {cap: v}})
    return out


def state_where(
    entry, checks, fields, sheet, public_only=False, defaults=None, lists=None
) -> list[str]:
    """Extract SQL conditions for a state. public_only: for a draft that leaves the
    terminal, so private filters are dropped and person values masked."""
    st = entry["state"]
    lists = lists or Lists()
    dims_sql = {c: d.sql for c, d in sheet.dims.items()}
    person = _person_captions(checks) if public_only else {}
    out = []
    for caption, value in _own_filters(entry, defaults, lists, _keyed_dims(checks)):
        f = (
            (checks["filters"].get(caption) or {}).get("sql")
            or lists.column(caption)
            or (fields.get(caption) or {}).get("field")
            or dims_sql.get(caption)
        )
        if not f or value is None:
            continue
        if isinstance(value, list):
            vals = [person.get(caption, v) for v in value]
            out.append(
                f"cast({f} as string) in ({', '.join(_sql_lit(v) for v in vals)})"
            )
            continue
        if caption in person and value not in (ALL, BLANK):
            value = person[caption]
        if c := _cond(f, value):
            out.append(c)
    for caption, value in (st.get("params") or {}).items():
        if sql := checks["param_where"].get(caption, {}).get(value):
            out.append(sql)
    for f in [*checks["extract_filters"], *sheet.extract_filters]:
        if f.get("datasource") not in (None, sheet.datasource):
            continue
        if public_only and f.get("private"):
            continue
        out.append(f["sql"])
    return out


def _own_sql(meas) -> tuple[str | None, str | None, str | None]:
    """The measure's SQL, with every aggregate limited by its own `where`."""
    if not meas.where:
        return meas.sql, meas.num, meas.den

    def own(s: str | None) -> str | None:
        return _filtered(s, meas.where) if s else None

    return own(meas.sql), own(meas.num), own(meas.den)


def extract_sql(sheet, meas, grain, where, lists=None) -> str:
    sel = [f"{_dim_sql(sheet, d, lists)} as g{i}" for i, d in enumerate(grain)]
    sql_, num, den = _own_sql(meas)
    sel += [f"{sql_} as m"] if sql_ else [f"{num} as m_num", f"{den} as m_den"]
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


def counts_sql(sheet, grain, where, student, lists=None) -> str:
    sel = [f"{_dim_sql(sheet, d, lists)} as g{i}" for i, d in enumerate(grain)]
    sel.append(f"count(distinct {student}) as n")
    # trunk-ignore(bandit/B608): SQL over the dashboard's own extract or rpt_ table; names come from the checks file
    sql = f"select {', '.join(sel)} from `{EXTRACT_TABLE}`"
    if where:
        sql += " where " + " and ".join(f"({w})" for w in where)
    if grain:
        sql += " group by " + ", ".join(str(i + 1) for i in range(len(grain)))
    return sql


def extract_counts(rows, n_grain) -> dict[tuple, int | None]:
    return {
        tuple(norm_dim(r[f"g{i}"]) for i in range(n_grain)): _int(r.get("n"))
        for r in rows
    }


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


def _key_text(dim: Dim, value: str) -> str | None:
    """The join key inside a displayed label (Tableau shows a section as
    "G5 - <teacher> - 501"; the key is 501): the first key pattern that matches.
    None when none does; the value itself when the dimension has no pattern."""
    if not dim.keys:
        return value
    for pattern in dim.keys:
        if m := re.search(pattern, value):
            return m.group(1) or None
    return None


def _keyed_dims(checks: dict) -> dict[str, Dim]:
    return {
        c: d for s in checks["sheets"].values() for c, d in s.dims.items() if d.keys
    }


def tableau_key(sheet: SheetMap, caption: str, value) -> str:
    """The join key in a value Tableau shows: the dimension's key pattern, if any,
    then its alias lookup."""
    dim = sheet.dims.get(caption)
    if dim is not None and isinstance(value, str):
        found = _key_text(dim, value)
        value = value if found is None else found
        if dim.values:
            value = dim.values.get(value.strip(), value)
    return norm_dim(value)


def _key(c: Cell, grain, sheet: SheetMap | None = None) -> tuple:
    if sheet is None:
        return tuple(norm_dim(c.key[d]) for d in grain)
    return tuple(tableau_key(sheet, d, c.key[d]) for d in grain)


def _reproduces(value, c: Cell, meas: Measure) -> bool:
    return matches_cell(value, c.shown, meas.round)


def _slice(
    entry,
    sname,
    checks,
    fields,
    defaults=None,
    sheet_filters=None,
    lists=None,
    public_only=False,
) -> tuple[list[str], list[dict]]:
    """One sheet's slice in a state, on both sides: the state's filters, the
    dashboard defaults the sheet keeps, and the sheet's saved filters."""
    sheet = checks["sheets"][sname]
    saved = (sheet_filters or {}).get(sname, [])
    dflt = sheet_defaults((defaults or {}).get(entry["state"]["dashboard"]), saved)
    saved_where, saved_cube, _ = sheet_conditions(saved, entry, checks, public_only)
    where = state_where(entry, checks, fields, sheet, public_only, dflt, lists)
    cube = (
        state_filters(entry, checks, dflt, lists)[0]
        + hard_filters(checks, sheet, public_only)
        + saved_cube
    )
    return where + saved_where, cube


def _extract_measure(sheet, meas, grain, where, run, lists=None) -> dict:
    if meas.diff:
        a, b = (
            _extract_measure(sheet, sheet.measures[x], grain, where, run, lists)
            for x in meas.diff
        )
        return _minus(a, b)
    rows = run(sheet.datasource, extract_sql(sheet, meas, list(grain), where, lists))
    return apply_calc(meas, extract_values(rows, len(grain)), 1.0)


def _trust(
    cells,
    checks,
    states,
    fields,
    run_extract,
    defaults=None,
    sheet_filters=None,
    lists=None,
) -> dict[tuple, float]:
    """The share of each (sheet, measure, grain)'s comparable cells, over every
    state, that the extract SQL reproduces. Sets each judged cell's `reproduces`;
    explain still checks every mismatched cell on its own."""
    pools: dict[tuple, dict[str, list[Cell]]] = {}
    for c in cells:
        if c.status in ("match", "mismatch") and (c.shown or "").strip():
            key = (c.sheet, c.measure, _grain(c)[0])
            pools.setdefault(key, {}).setdefault(c.state, []).append(c)
    out = {}
    for (sname, mname, grain), by_state in pools.items():
        sheet = checks["sheets"][sname]
        meas = sheet.measures[mname]
        hits_all = []
        for state, mine in sorted(by_state.items()):
            where, _ = _slice(
                states[state], sname, checks, fields, defaults, sheet_filters, lists
            )
            try:
                ext = _extract_measure(sheet, meas, grain, where, run_extract, lists)
            except Exception:  # noqa: BLE001 - SQL the extract cannot run reproduces nothing
                ext = {}
            index = Keys(ext, _multi(sheet, grain))
            for c in mine:
                hits = index.find(_key(c, grain, sheet))
                value = ext.get(hits[0]) if len(hits) == 1 else None
                c.reproduces = _reproduces(value, c, meas)
                hits_all.append(c.reproduces)
        out[(sname, mname, grain)] = sum(hits_all) / len(hits_all)
    return out


def _cube_queries(sheet, meas, grain, filters, student=None) -> list[dict]:
    """The Cube queries behind one measure at a grain, its own filters on top."""
    if meas.diff:
        return [
            q
            for x in meas.diff
            for q in _cube_queries(sheet, sheet.measures[x], grain, filters, student)
        ]
    return [cube_query(sheet, grain, [meas.cube, student], filters + meas.cube_filters)]


def _cube_raw(sheet, meas, grain, filters, ask, student, lists) -> tuple[dict, dict]:
    """A plain measure's raw Cube values and student counts, asked per bin when
    the grain holds a group dimension, as compare asks."""
    split = _bins(sheet, grain, lists)
    if split is None:
        (q,) = _cube_queries(sheet, meas, grain, filters, student)
        by = _by_key(ask(q), sheet, grain)
        raw = {k: _num(r.get(meas.cube)) for k, r in by.items()}
        counts = {k: _int(r.get(student)) for k, r in by.items()} if student else {}
        return raw, counts
    i, rest, each = split
    raw, counts = {}, {}
    for b, only in each:
        part, n = _cube_raw(sheet, meas, rest, [*filters, only], ask, student, lists)
        raw.update(_rekey(part, i, b))
        counts.update(_rekey(n, i, b))
    return raw, counts


def _cube_measure(
    sheet, meas, grain, filters, ask, student=None, lists=None
) -> tuple[dict, dict]:
    """A measure's Cube values (its table calculation applied) and student counts."""
    if meas.diff:
        (a, n), (b, _) = (
            _cube_measure(sheet, sheet.measures[x], grain, filters, ask, student, lists)
            for x in meas.diff
        )
        return _minus(a, b), n
    raw, counts = _cube_raw(sheet, meas, grain, filters, ask, student, lists or Lists())
    return apply_calc(meas, raw, meas.scale), counts


def _variant(
    v, sheet, meas, grain, where, base, run_extract, load, student=None, lists=None
):
    dash = None
    if v.get("where"):
        alt = Measure(
            meas.caption,
            meas.cube,
            table_calc=meas.table_calc,
            sql=_filtered(meas.sql, v["where"]) if meas.sql else None,
            num=None if meas.sql else _filtered(meas.num, v["where"]),
            den=None if meas.sql else _filtered(meas.den, v["where"]),
            where=meas.where,
        )
    elif v.get("sql") or v.get("num"):
        alt = Measure(
            meas.caption,
            meas.cube,
            sql=v.get("sql"),
            num=v.get("num"),
            den=v.get("den"),
            table_calc=meas.table_calc,
            where=meas.where,
        )
    else:
        alt = None
    if alt is not None:
        rows = run_extract(
            sheet.datasource, extract_sql(sheet, alt, list(grain), where, lists)
        )
        dash = apply_calc(alt, extract_values(rows, len(grain)), 1.0)
    cube = (
        _cube_measure(
            sheet,
            meas,
            grain,
            base + v["cube_filters"],
            lambda q: load(q)[0],
            student,
            lists,
        )[0]
        if v.get("cube_filters")
        else None
    )
    return v["explains"], dash, cube


@dataclass
class Live:
    """The live warehouse side of the timing check."""

    rows: Callable[[str, str], list[dict]]  # extract SQL run on the live rpt_ table
    modified: Callable[[str], dt.datetime | None]  # when that table last changed
    # Cube's current answer to a query, and its lastRefreshTime
    cube_now: Callable[[dict], tuple[list[dict], dt.datetime | None]]


def explain_cells(
    cells,
    checks,
    states,
    fields,
    run_extract,
    load,
    live=None,
    defaults=None,
    sheet_filters=None,
    lists=None,
    on_batch: Callable[[], None] | None = None,
) -> None:
    sides = fix_sides(checks)
    batches: dict[tuple, list[Cell]] = {}
    for c in cells:
        # Every run starts fresh, so an explanation removed from the checks file goes.
        c.verdict, c.why, c.explained_by = None, "", []
        c.extract = c.variant = c.cube_variant = None
        c.reproduces = None
        c.live = c.live_students = c.cube_students = None
        c.gap = ""
        sheet = checks["sheets"].get(c.sheet)
        if c.status != "not_comparable" and (
            sheet is None or c.measure not in sheet.measures
        ):
            c.why = "no longer mapped in the checks file; run compare --redo"
        elif c.status == "match":
            c.verdict = "pass"
        elif c.status == "missing_member":
            c.verdict = "missing_member"
        elif c.status == "mismatch" and c.routes:
            c.explained_by = [ROUTES]
            c.verdict = cell_verdict(c, sides, sheet.measures[c.measure])
        elif c.status == "mismatch":
            key = (c.sheet, c.state, _grain(c)[0], c.measure)
            batches.setdefault(key, []).append(c)
    mapped = [c for c in cells if not c.why]
    trusted = _trust(
        mapped, checks, states, fields, run_extract, defaults, sheet_filters, lists
    )
    for (sname, state, grain, mname), batch in batches.items():
        try:
            _explain_batch(
                sname,
                state,
                grain,
                mname,
                batch,
                checks,
                states,
                fields,
                run_extract,
                load,
                live,
                defaults,
                sheet_filters,
                trusted,
                sides,
                lists=lists,
            )
        except Exception as err:  # noqa: BLE001 - one batch's failure blames nobody
            # A query Cube or the warehouse cannot answer, or SQL the extract cannot
            # run, leaves only its own cells undecided.
            label = "Cube error" if isinstance(err, CubeError) else type(err).__name__
            for c in batch:
                c.verdict, c.why = "incomplete", f"{label}: {err}"[:300]
        if on_batch is not None:
            on_batch()


def _explain_batch(
    sname,
    state,
    grain,
    mname,
    batch,
    checks,
    states,
    fields,
    run_extract,
    load,
    live,
    defaults,
    sheet_filters,
    trusted,
    sides,
    lists=None,
) -> None:
    """Judge one sheet, state, grain and measure's mismatched cells."""
    sheet = checks["sheets"][sname]
    meas = sheet.measures[mname]
    rate = trusted.get((sname, mname, grain), 0.0)
    if rate < TRUST:
        for c in batch:
            c.verdict = "incomplete"
            c.why = (
                f"extract SQL reproduces {rate:.0%} of this measure's cells at this "
                f"grain; {TRUST:.0%} needed"
            )
        return
    where, base = _slice(
        states[state], sname, checks, fields, defaults, sheet_filters, lists
    )
    ext = _extract_measure(sheet, meas, grain, where, run_extract, lists)
    live_v, cube_now, cube_at, table_at = None, None, None, None
    live_n, cube_n = {}, {}
    if live is not None:
        live_v = _extract_measure(sheet, meas, grain, where, live.rows, lists)
        refreshed = []

        def ask_now(q):
            rows_, at = live.cube_now(q)
            refreshed.append(at)
            return rows_

        # Same shape as compare's query, so Cube routes it the same way.
        cube_now, cube_n = _cube_measure(
            sheet, meas, grain, base, ask_now, checks["student_count"], lists
        )
        cube_at = refreshed[-1] if refreshed else None
        student_col = checks.get("student_column", "student_number")
        live_n = extract_counts(
            live.rows(
                sheet.datasource, counts_sql(sheet, grain, where, student_col, lists)
            ),
            len(grain),
        )
        table_at = live.modified(sheet.datasource)
    variants = [
        _variant(
            v,
            sheet,
            meas,
            grain,
            where,
            base,
            run_extract,
            load,
            checks["student_count"],
            lists,
        )
        for v in meas.variants
    ]
    index = Keys(ext, _multi(sheet, grain))
    for c in batch:
        k0 = _key(c, grain, sheet)
        hits = index.find(k0)
        k = hits[0] if len(hits) == 1 else k0
        c.extract = ext.get(k)
        if not _reproduces(c.extract, c, meas):
            c.verdict, c.why = (
                "incomplete",
                "extract SQL does not reproduce this cell",
            )
            continue
        if cube_now is not None:
            # Judge Cube as it is now: compare may have run before its refresh.
            c.cube = cube_now.get(k)
            if _reproduces(c.cube, c, meas):
                c.verdict, c.why = (
                    "pass",
                    "Cube matches Tableau after its latest refresh",
                )
                continue
        if live_v is not None and matches_raw(live_v.get(k), c.cube):
            c.verdict = "pass"
            c.why = (
                "timing: the extract is older than Cube; Cube matches the live table"
            )
            continue
        for names, dash, cube in variants:
            d_v = c.extract if dash is None else dash.get(k)
            c_v = c.cube if cube is None else cube.get(k)
            if matches_raw(c_v, d_v):
                c.explained_by, c.variant = list(names), d_v
                c.cube_variant = None if cube is None else c_v
                break
        c.verdict = cell_verdict(c, sides, meas)
        accepted = [
            n for n in c.explained_by if n in sides.get("accepted", frozenset())
        ]
        if c.verdict == "pass" and accepted:
            c.why = "accepted difference, see " + ", ".join(
                f"#{checks['mismatches'][n]['issue']}" for n in accepted
            )
        if c.verdict != "fail" or live is None:
            continue
        c.live = None if live_v is None else live_v.get(k)
        c.live_students, c.cube_students = live_n.get(k), cube_n.get(k)
        if cube_at and table_at and cube_at < table_at:
            c.verdict = "incomplete"
            c.why = (
                f"Cube's data (refreshed {cube_at:%Y-%m-%d %H:%M}) is older than the live "
                f"table (built {table_at:%Y-%m-%d %H:%M}); re-run explain after Cube refreshes"
            )
            continue
        c.gap = "row gap" if c.live_students != c.cube_students else "formula gap"
        c.why = (
            f"{c.gap}: Cube {_fmt(c.cube)}, live table {_fmt(c.live)}; students: "
            f"Cube {c.cube_students}, live table {c.live_students}"
        )
        if cube_at and table_at:
            c.why += (
                f" (Cube refreshed {cube_at:%Y-%m-%d %H:%M}, the live table built "
                f"{table_at:%Y-%m-%d %H:%M})"
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
    # A run replaces its dashboard's entries, so a corrected row id leaves none stale.
    data = {gid: r for gid, r in data.items() if r.get("dashboard") != workbook}
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
    ("accepted", "Accepted differences"),
)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _fmt(v) -> str:
    return "nothing" if v is None else f"{v:.4g}"


UNKEYED = "a label the key pattern does not match"


def masked_key(c: Cell, checks: dict) -> dict[str, str]:
    """A cell's key as outputs may show it: a person as their label, a keyed
    label as its key only."""
    sheet = checks["sheets"].get(c.sheet)
    dims = sheet.dims if sheet else {}
    out = {}
    for d, v in c.key.items():
        dim = dims.get(d)
        if dim is not None and dim.person:
            out[d] = dim.person if isinstance(dim.person, str) else "a student"
        elif dim is not None and dim.keys and v != TOTAL:
            out[d] = _key_text(dim, v) or UNKEYED
        else:
            out[d] = v
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


def coverage_markdown(states, cells, checks=None) -> str:
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
    bad = _coarsest([c for c in cells if c.reproduces is False])
    if bad:
        lines += ["", f"Cells the extract SQL does not reproduce: {len(bad)}"]
        for c in bad[:50]:
            where = _where_text(c, checks) if checks else "a cell"
            small = "" if (c.n_students or 0) >= SMALL_CELL else " (small cell)"
            lines.append(f"- {c.state}: {c.sheet} / {c.measure}, {where}{small}")
    routes = {
        (c.sheet, c.state, _grain(c)[0]): (
            ", ".join(c.rollups) or "raw",
            ", ".join(c.rollups_alone) or "raw",
        )
        for c in cells
        if c.status in ("match", "mismatch")
    }
    if routes:
        lines += [
            "",
            "Cube routes, by query (with the student count / alone):",
            *(
                f"- {w} / {a}: {n}"
                for (w, a), n in Counter(routes.values()).most_common()
            ),
        ]
    return "\n".join(lines) + "\n"


def _typical_gap(cells) -> str:
    """The median gap between Cube and Tableau, relative to what Tableau shows: a
    0.3% shortfall everywhere reads differently from a 20-point cell."""
    rel = [
        abs(c.cube - c.tableau) / abs(c.tableau)
        for c in cells
        if c.cube is not None and c.tableau
    ]
    return f"{statistics.median(rel):.1%}" if rel else "unknown"


def _investigate_sql(
    c, checks, states, fields, defaults, sheet_filters, lists
) -> list[str]:
    """The trusted extract SQL for a fail cell, and the same SQL on the live table.
    A diff measure prints one pair per part."""
    sheet = checks["sheets"][c.sheet]
    meas = sheet.measures[c.measure]
    where, _ = _slice(
        states[c.state],
        c.sheet,
        checks,
        fields,
        defaults,
        sheet_filters,
        lists,
        public_only=True,
    )
    out: list[str] = []
    for name in meas.diff or (c.measure,):
        sql = extract_sql(
            sheet, sheet.measures[name], list(_grain(c)[0]), where, lists=lists
        )
        try:
            live = sql.replace(
                f"`{EXTRACT_TABLE}`", f"`{live_table(sheet.datasource)}`"
            )
        except CheckError as err:
            live = f"-- {err}"
        part = f" ({name})" if meas.diff else ""
        out += [
            "",
            f"  Over the extract (what Tableau showed){part}:",
            "",
            "  ```sql",
            f"  {sql}",
            "  ```",
            "",
            f"  Over the live table{part}:",
            "",
            "  ```sql",
            f"  {live}",
            "  ```",
        ]
    return out


def digest_markdown(
    workbook,
    cells,
    checks,
    states=None,
    fields=None,
    defaults=None,
    sheet_filters=None,
    lists=None,
) -> str:
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
        lines += ["", "## Investigate"]
        for gap, title in (
            ("row gap", "Row gaps: Cube and the live table count different students"),
            ("formula gap", "Formula gaps: the same students, a different value"),
            ("", "No live check"),
        ):
            mine = [c for c in fails if c.gap == gap]
            if not mine:
                continue
            lines += ["", f"### {title}", ""]
            by: dict[tuple, list[Cell]] = {}
            for c in mine:
                by.setdefault((c.sheet, c.measure), []).append(c)
            for (sheet, measure), cs in sorted(by.items(), key=lambda x: -len(x[1])):
                lines.append(
                    f"- {sheet} / {measure}: {len(cs)} cells, typical gap {_typical_gap(cs)}"
                )
                lines += [f"  - {_example(c, checks)}" for c in cs[:3]]
                if states is not None:
                    lines += _investigate_sql(
                        cs[0],
                        checks,
                        states,
                        fields or {},
                        defaults,
                        sheet_filters,
                        lists,
                    )
    unsure = Counter(c.why or c.reason for c in cells if c.verdict == "incomplete")
    if unsure:
        lines += [
            "",
            "## Could not tell",
            "",
            *(f"- {r}: {n} cells" for r, n in unsure.most_common()),
        ]
    return "\n".join(lines) + "\n"


def _public_filters(filters: list[dict], checks: dict) -> list[dict]:
    """Cube filters fit to leave the terminal: a person's values become their label,
    under any operator and inside `or`/`and` groups."""
    members = _caption_members(checks)
    label = {
        members[c]: lab for c, lab in _person_captions(checks).items() if c in members
    }

    def clean(f: dict) -> dict:
        for k in ("or", "and"):
            if k in f:
                return {**f, k: [clean(x) for x in f[k]]}
        if f.get("member") in label and f.get("values"):
            return {**f, "values": [label[f["member"]]]}
        return f

    return [clean(f) for f in filters]


_CHECK_YOURSELF = (
    "Both queries below read live data, so they agree once the fix is in. Before "
    "you compare them, check that Cube's `lastRefreshTime` (in its `/load` answer) "
    "is not older than the table's last-modified time; if either is behind, wait "
    "and run both again. The dashboard's numbers above are evidence, not the test. "
    "A fix inside the Tableau workbook is checked only by the analyst's next export."
)


def issue_drafts(
    workbook,
    cells,
    checks,
    states,
    fields,
    defaults=None,
    sheet_filters=None,
    lists=None,
) -> dict[str, str]:
    out = {}
    for s, m in checks["mismatches"].items():
        mine = _coarsest([c for c in cells if s in c.explained_by])
        if m.get("issue") or not mine:
            continue
        first = mine[0]
        sheet = checks["sheets"][first.sheet]
        meas = sheet.measures[first.measure]
        grain = list(_grain(first)[0])
        where, cube_filters = _slice(
            states[first.state],
            first.sheet,
            checks,
            fields,
            defaults,
            sheet_filters,
            lists,
            public_only=True,
        )
        # A diff measure has no SQL of its own: one query per part.
        parts = [
            (name, extract_sql(sheet, sheet.measures[name], grain, where, lists))
            for name in meas.diff or (first.measure,)
        ]
        tag = (lambda n: f"-- {n}\n") if meas.diff else (lambda n: "")
        query = "\n\n".join(tag(n) + q for n, q in parts)
        cube_qs = _cube_queries(
            sheet, meas, grain, _public_filters(cube_filters, checks)
        )
        try:
            live_sql = query.replace(
                f"`{EXTRACT_TABLE}`", f"`{live_table(sheet.datasource)}`"
            )
        except CheckError as err:
            live_sql = f"-- {err}"
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
            "## Check it yourself",
            "",
            _CHECK_YOURSELF,
            "",
            "Cube `/load`:",
            "",
            "```json",
            *(json.dumps({"query": q}, indent=2) for q in cube_qs),
            "```",
            "",
            "The same measure on the live table:",
            "",
            "```sql",
            live_sql,
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
            f"mismatch `{s}`. A builder verifies with 'Check it yourself'; the analyst's "
            "follow-up run confirms the cells turn `pass`.",
            "",
            "</details>",
        ]
        out[s] = "\n".join(body) + "\n"
    return out


def write_outputs(
    out_dir,
    workbook,
    run_date,
    cells,
    checks,
    states,
    fields,
    defaults=None,
    sheet_filters=None,
    lists=None,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{run_date}-{_slug(workbook)}"
    (out / f"{stem}-coverage.md").write_text(coverage_markdown(states, cells, checks))
    digest = out / f"{stem}-digest.md"
    digest.write_text(
        digest_markdown(
            workbook, cells, checks, states, fields, defaults, sheet_filters, lists
        )
    )
    drafts = issue_drafts(
        workbook, cells, checks, states, fields, defaults, sheet_filters, lists
    )
    if drafts:
        (out / f"{stem}-issues").mkdir(exist_ok=True)
        for s, text in drafts.items():
            (out / f"{stem}-issues" / f"{s}.md").write_text(text)
    write_latest(out / "latest.json", workbook, run_date, row_results(cells, checks))
    return digest


SNAPSHOT_ROOT = Path.home() / ".cache" / "cube-validate"


# Tableau names an aggregated column "<prefix><caption>" in an export header.
AGG_PREFIXES = (
    "Avg. ",
    "Sum of ",
    "Distinct count of ",
    "Count of ",
    "% of Total ",
    "Running Sum of ",
    "Max. ",
    "Min. ",
    "Median of ",
)
_AGG = re.compile(r"\b(AVG|SUM|COUNTD?|MIN|MAX|MEDIAN|TOTAL|WINDOW_\w+)\(", re.I)


def column_formulas(twb_text: str) -> dict[str, dict]:
    """Each workbook column by caption, with its datasource, field and formula."""
    import defusedxml.ElementTree as SafeET

    out: dict[str, dict] = {}
    for ds in SafeET.fromstring(twb_text).iter("datasource"):
        source = ds.get("caption") or ds.get("name") or ""
        for col in ds.findall("column"):
            name = (col.get("name") or "").strip("[]")
            calc = col.find("calculation")
            out.setdefault(
                col.get("caption") or name,
                {
                    "datasource": source,
                    "field": name,
                    "formula": calc.get("formula") if calc is not None else None,
                },
            )
    return out


def header_column(header: str, formulas: dict) -> tuple[str, dict | None]:
    """The workbook column behind an exported header, after Tableau's prefix."""
    if header in formulas:
        return header, formulas[header]
    for p in AGG_PREFIXES:
        if header.startswith(p) and header[len(p) :] in formulas:
            return header[len(p) :], formulas[header[len(p) :]]
    return header, None


def candidates(field: str, caption: str, members: list[str]) -> list[str]:
    """Cube members whose short name is the field or the caption: a draft only."""
    want = {field.lower(), _slug(caption).replace("-", "_")}
    return [m for m in members if m.split(".", 1)[-1] in want]


def draft_map(snapdir: Path, members: list[str]) -> dict:
    """A draft of sheets: for the analyst to edit, from each exported sheet's
    header, the workbook's formula for each column, and Cube's members."""
    snapdir = Path(snapdir)
    formulas = column_formulas((snapdir / "review.twb").read_text(encoding="utf-8"))
    m = json.loads((snapdir / "manifest.json").read_text())
    headers: dict[str, list[str]] = {}
    for _, e in sorted(m["states"].items()):
        if e.get("status") != "ok":
            continue
        for sheet, meta in e["sheets"].items():
            if sheet not in headers:
                headers[sheet] = read_export(
                    (snapdir / meta["file"]).read_bytes()
                ).columns
    out: dict[str, dict] = {}
    for sheet, cols in headers.items():
        out[sheet] = {}
        for h in cols:
            name, col = header_column(h, formulas)
            formula = col["formula"] if col else None
            prefixed = name != h
            out[sheet][h] = {
                "kind": "measure"
                if prefixed or _AGG.search(formula or "")
                else "dimension",
                "formula": formula,
                "field": col["field"] if col else None,
                "datasource": col["datasource"] if col else None,
                "cube_candidates": candidates(
                    col["field"] if col else name, name, members
                ),
            }
    return out


def _map(a) -> int:
    checks = load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    draft = draft_map(snapdir, _client().meta())
    (snapdir / "map.yml").write_text(
        yaml.safe_dump(draft, sort_keys=False, allow_unicode=True)
    )
    print(f"map draft: {len(draft)} sheets -> {snapdir / 'map.yml'}")
    return 0


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


def ignored_filter_leaks(
    saved, entry, checks, fields, sheet, run_extract, defaults=None, lists=None
) -> list[tuple[str, int]]:
    """Rows in the state's slice that an ignored saved filter would have hidden.
    ignore_sheet_filters is safe only while this is 0; a FIXED-LOD filter has no
    extract column, so the checks file links its issue instead."""
    ignored = set(checks["ignore_sheet_filters"])
    if not ignored:
        return []
    kept = [f for f in saved if f["caption"] not in ignored]
    where = state_where(entry, checks, fields, sheet, defaults=defaults, lists=lists)
    where += sheet_conditions(kept, entry, checks)[0]
    plain = {**checks, "ignore_sheet_filters": []}
    out = []
    for f in saved:
        if f["caption"] not in ignored or f.get("calculated"):
            continue
        cond = sheet_conditions([f], entry, plain)[0]
        if not cond:
            continue
        fails = f"not coalesce(({' and '.join(cond)}), false)"
        sql = (
            # trunk-ignore(bandit/B608): SQL over the dashboard's own extract; names come from the workbook
            f"select count(*) as n from `{EXTRACT_TABLE}` where "
            + " and ".join(f"({w})" for w in [*where, fails])
        )
        n = int(run_extract(sheet.datasource, sql)[0]["n"])
        if n:
            out.append((f["caption"], n))
    return out


def run_compare(
    checks, snapdir, load, extracts, redo=False, warn: Callable[[str], None] = print
):
    """Compare every exported state not compared yet (every state with redo, after a
    mapping changed), and propose the next descent level."""
    snapdir = Path(snapdir)
    m = json.loads((snapdir / "manifest.json").read_text())
    lists = Lists.of(m)
    before = [] if redo else read_cells(snapdir / "cells.jsonl")
    done = {c.state for c in before}
    cells: list[Cell] = []
    for sid, e in sorted(m["states"].items()):
        if e.get("status") != "ok" or sid in done:
            continue
        dflt = (m.get("defaults") or {}).get(e["state"]["dashboard"])
        filters, missing = state_filters(e, checks, dflt, lists)
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
            saved = (m.get("sheet_filters") or {}).get(sheet_name, [])
            kept = sheet_defaults(dflt, saved)
            try:
                _, sheet_cube, sheet_missing = sheet_conditions(saved, e, checks)
                filters, missing = state_filters(e, checks, kept, lists)
                cells += compare_export(
                    sheet,
                    sid,
                    export,
                    load,
                    filters + sheet_cube,
                    missing + sheet_missing,
                    checks,
                    lists,
                )
            except CubeError as err:
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
                        f"Cube error: {err}",
                    )
                )
            try:
                for cap, n in ignored_filter_leaks(
                    saved, e, checks, m["fields"], sheet, extracts, kept, lists
                ):
                    warn(
                        f"{sid} / {sheet_name}: {n} rows in this slice fail the "
                        f"ignored filter {cap}"
                    )
            except Exception as err:  # noqa: BLE001 - the check only warns
                warn(
                    f"{sid} / {sheet_name}: could not check the ignored saved filters: {err}"
                )
    every = before + cells

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
        members=set(_caption_members(checks)),
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

    def cube_now(q):
        rows_, _ = client.load(q)
        t = client.last_refresh
        return rows_, dt.datetime.fromisoformat(t.replace("Z", "+00:00")) if t else None

    return Live(rows, modified, cube_now)


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
        cells, nxt = run_compare(checks, snapdir, client.load, extracts, a.redo)
    finally:
        extracts.close()
    before = [] if a.redo else read_cells(snapdir / "cells.jsonl")
    write_cells(snapdir / "cells.jsonl", before + cells)
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
            m.get("defaults"),
            m.get("sheet_filters"),
            lists=Lists.of(m),
            on_batch=lambda: write_cells(snapdir / "cells.jsonl", cells),
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
        m.get("defaults"),
        m.get("sheet_filters"),
        lists=Lists.of(m),
    )
    print(f"digest: {digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cube_validate")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare")
    c.add_argument("checks")
    c.add_argument(
        "--redo", action="store_true", help="recompare states already compared"
    )
    sub.add_parser("explain").add_argument("checks")
    sub.add_parser("map").add_argument("checks")
    d = sub.add_parser("drafts")
    d.add_argument("checks")
    d.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    return {"compare": _compare, "explain": _explain, "drafts": _drafts, "map": _map}[
        a.cmd
    ](a)


if __name__ == "__main__":
    raise SystemExit(main())
