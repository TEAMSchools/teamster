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
