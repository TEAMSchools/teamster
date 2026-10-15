"""Cube side of a capture: rows by day, aggregate answers, each stamped."""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import cells
from .hyper import write_table

CUBE_LIMIT = 50_000
DEFAULT_CUBE_URL = (
    "https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1"
)
USER_EMAIL_CACHE = Path.home() / ".config" / "teamster" / "cube-user-email"
HYPER_TYPES = {"number": "double", "time": "date", "boolean": "bool", "string": "text"}


class CubeError(RuntimeError):
    """Cube returned an error."""


class CaptureError(RuntimeError):
    """Capture could not freeze a complete, current answer; names the parts."""


@dataclass
class LoadResult:
    data: list[dict]
    last_refresh: str | None
    total: int | None


def _httpx_client():
    import httpx

    return httpx.Client(timeout=120)


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
        """One HTTP client per thread, so parallel runs never share a pool."""
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

    def _post(self, path: str, query: dict) -> dict:
        import httpx

        overloaded = 0
        for _ in range(120):
            try:
                r = self._http().post(
                    f"{self.url}/{path}",
                    json={"query": query},
                    headers={"Authorization": self._token()},
                )
            except httpx.TransportError as err:
                if overloaded >= 5:
                    raise CubeError(f"Cube connection failed: {err}") from err
                overloaded += 1
                self.sleep(2**overloaded)
                continue
            if r.status_code in (429, 502, 503, 504) and overloaded < 5:
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
            return body
        raise CubeError("gave up after 120 'Continue wait' responses")

    def load(self, query: dict, renew: bool = False) -> LoadResult:
        """Rows with this answer's own lastRefreshTime and total."""
        q = {**query, "renewQuery": True} if renew else query
        body = self._post("load", q)
        return LoadResult(
            body.get("data", []), body.get("lastRefreshTime"), body.get("total")
        )

    def sql(self, query: dict) -> tuple[str, list]:
        """The BigQuery SQL and parameters Cube compiles; touches no data."""
        body = self._post("sql", query)
        sql, params = body["sql"]["sql"]
        return sql, list(params)

    def member_types(self, view: str) -> dict[str, str]:
        r = self._http().get(
            f"{self.url}/meta", headers={"Authorization": self._token()}
        )
        for c in r.json().get("cubes", []):
            if c["name"] == view:
                return {
                    m["name"].split(".", 1)[1]: m["type"]
                    for kind in ("measures", "dimensions")
                    for m in c.get(kind, [])
                }
        raise CubeError(f"view {view} is not visible to {self.email}")


def client_from_env() -> CubeClient:
    email = os.environ.get("CUBE_USER_EMAIL", "").strip()
    if not email and USER_EMAIL_CACHE.exists():
        email = USER_EMAIL_CACHE.read_text().strip()
    if not email:
        raise CubeError("no Cube identity: set CUBE_USER_EMAIL")
    return CubeClient(
        os.environ.get("CUBE_API_URL", DEFAULT_CUBE_URL),
        os.environ["CUBE_API_SECRET"],
        email,
    )


def row_queries(checks, start: dt.date, end: dt.date) -> list[tuple[str, dict]]:
    """1 ungrouped query per day, so each prunes to 1 date partition."""
    v = checks.cube.view
    out = []
    d = start
    while d <= end:
        day = d.isoformat()
        out.append(
            (
                day,
                {
                    "dimensions": [f"{v}.{m}" for m in checks.cube.members],
                    "filters": [
                        {
                            "member": f"{v}.{checks.cube.date}",
                            "operator": "inDateRange",
                            "values": [day, day],
                        },
                        *checks.cube.filters,
                    ],
                    "ungrouped": True,
                    "limit": CUBE_LIMIT,
                    "total": True,
                },
            )
        )
        d += dt.timedelta(days=1)
    return out


def _ts(s: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def _current(client, query: dict, built_at: dt.datetime) -> tuple[LoadResult, str]:
    """An answer no older than built_at, asking once more if needed."""
    r = client.load(query)
    stamp = _ts(r.last_refresh)
    if stamp is None or stamp < built_at:
        r = client.load(query, renew=True)
        stamp = _ts(r.last_refresh)
        if stamp is None:
            return r, "answer has no lastRefreshTime"
        if stamp < built_at:
            return (
                r,
                f"answer from {r.last_refresh} is older than the build at {built_at.isoformat()}",
            )
    return r, ""


def pull_rows(
    client,
    snap,
    parts: list[tuple[str, dict]],
    built_at: dt.datetime,
    workers: int = 8,
) -> dict[str, dict]:
    """Capture every part; a part is written only when complete and current.

    Raises:
        CaptureError: Any part was short, hit the row limit, or stayed stale.
    """
    report: dict[str, dict] = {}

    def one(part: tuple[str, dict]) -> tuple[str, dict]:
        pid, q = part
        path = snap.cube_parts / f"{pid}.json"
        if path.exists():
            return pid, {"status": "kept"}
        try:
            r, stale = _current(client, q, built_at)
        except CubeError as e:
            return pid, {"status": "failed", "why": str(e)}
        if stale:
            return pid, {"status": "failed", "why": stale}
        if r.total is None or len(r.data) != r.total:
            return pid, {"status": "failed", "why": f"{len(r.data)} of {r.total} rows"}
        if len(r.data) >= CUBE_LIMIT:
            return pid, {"status": "failed", "why": f"hit the {CUBE_LIMIT}-row limit"}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"rows": r.data, "total": r.total, "last_refresh": r.last_refresh}
            )
        )
        os.replace(tmp, path)
        return pid, {
            "status": "captured",
            "rows": len(r.data),
            "last_refresh": r.last_refresh,
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for pid, rep in pool.map(one, parts):
            report[pid] = rep
    failed = {p: r["why"] for p, r in report.items() if r["status"] == "failed"}
    if failed:
        raise CaptureError(
            "Cube parts failed: "
            + "; ".join(f"{p}: {w}" for p, w in sorted(failed.items()))
        )
    return report


def _cast(value, cube_type: str):
    if value is None:
        return None
    if cube_type == "number":
        return float(value)
    if cube_type == "time":
        return dt.date.fromisoformat(str(value)[:10])
    if cube_type == "boolean":
        return value if isinstance(value, bool) else str(value).lower() == "true"
    return str(value)


def write_cube_hyper(snap, checks, types: dict[str, str]) -> int:
    """cube.hyper from every part file; returns the rows written."""
    v, members = checks.cube.view, list(checks.cube.members)
    columns = [(m, HYPER_TYPES[types[m]]) for m in members]

    def rows():
        for f in sorted(snap.cube_parts.glob("*.json")):
            for r in json.loads(f.read_text())["rows"]:
                yield [_cast(r.get(f"{v}.{m}"), types[m]) for m in members]

    return write_table(snap.cube, "cube", "rows", columns, rows())


def scope_query(checks) -> dict | None:
    """1 grouped, undated count by the scope member; None without a scope key.

    It carries cube.filters, so a filter that drops a whole school drops it
    from the scope too.

    Cube rewrites every query to the caller's schools, so the values it returns
    are the scope. Rows captured for a period cannot stand in for it: a school
    with no rows that period would look out of scope.
    """
    if not checks.scope_key:
        return None
    member = next(e.cube for e in checks.key if e.name == checks.scope_key)
    v = checks.cube.view
    return {
        "dimensions": [f"{v}.{member}"],
        "measures": [f"{v}.count_students"],
        "filters": [*checks.cube.filters],
        "limit": CUBE_LIMIT,
        "total": True,
    }


def capture_scope(client, checks) -> list[str]:
    """The scope key's values Cube shows this identity, sorted.

    Raises:
        CaptureError: The scope answer failed, was short or hit the row limit.
    """
    q = scope_query(checks)
    if q is None:
        return []
    try:
        r = client.load(q)
    except CubeError as e:
        raise CaptureError(f"Cube scope query failed: {e}") from e
    if r.total is None or len(r.data) != r.total:
        raise CaptureError(f"Cube scope query returned {len(r.data)} of {r.total} rows")
    if len(r.data) >= CUBE_LIMIT:
        raise CaptureError(f"Cube scope query hit the {CUBE_LIMIT}-row limit")
    col = q["dimensions"][0]
    return sorted({str(x[col]) for x in r.data if x.get(col) is not None})


def capture_answers(
    client, snap, checks, manifest: dict, built_at: dt.datetime, workers: int = 8
) -> dict:
    """1 aggregate answer per (cut, sheet), with its query, SQL and refresh time."""
    jobs = []
    for cut in checks.cuts:
        meta = (manifest.get("cuts") or {}).get(cut.id, {})
        targets = set(meta.get("click_targets") or [])
        for sheet in checks.sheets:
            click = (meta.get("click_filters") or {}) if sheet in targets else {}
            jobs.append((cut, sheet, click))

    def one(job):
        cut, sheet, click = job
        key = cells.answer_key(cut.id, sheet)
        try:
            q = cells.cube_query(checks, sheet, cut, click)
        except cells.MappingGap as e:
            return key, {"error": f"not mapped: {e.args[0]}"}
        try:
            r, stale = _current(client, {**q, "total": True}, built_at)
            if stale:
                return key, {"query": q, "error": stale}
            if r.total is None or len(r.data) != r.total:
                return key, {"query": q, "error": f"{len(r.data)} of {r.total} rows"}
            if len(r.data) >= CUBE_LIMIT:
                return key, {"query": q, "error": f"hit the {CUBE_LIMIT}-row limit"}
            sql, _ = client.sql(q)
        except CubeError as e:
            return key, {"query": q, "error": str(e)}
        return key, {
            "query": q,
            "data": r.data,
            "last_refresh": r.last_refresh,
            "sql": sql,
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        answers = dict(pool.map(one, jobs))
    snap.answers.write_text(json.dumps(answers, indent=2))
    return answers
