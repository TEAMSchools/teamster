#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "mcp>=2.0",
#   "httpx>=0.27",
#   "pyjwt>=2.8",
# ]
# ///
"""MCP server wrapping Cube Cloud's REST data API.

Mints HS256 JWTs per request using CUBE_API_SECRET. The user's Google
Workspace email is the JWT security context — it determines which `cube-*`
groups apply per [src/cube/cube.js].

Email resolution (in order):
  1. CUBE_USER_EMAIL env var (override, bypasses cache).
  2. ~/.config/teamster/cube-user-email cache file.
  3. ctx.elicit() prompt — answer is cached for future sessions.
  4. If elicit isn't supported by the client, raise an error directing the
     engineer to set CUBE_USER_EMAIL or write the cache file directly.

Tools:
  meta  - return the Cube data model catalog (cached 1 hour per email)
  load  - run a Cube query (JSON body per the REST API spec)
  sql   - return the SQL Cube would generate for a query, without executing
"""

import asyncio
import contextlib
import hashlib
import json
import os
import sys
import time
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import jwt
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ClientCapabilities, ElicitationCapability
from pydantic import BaseModel, Field

CUBE_REST_URL = os.environ["CUBE_REST_URL"].rstrip("/")
CUBE_API_SECRET = os.environ["CUBE_API_SECRET"]
AUTHKIT_DOMAIN = os.environ.get("AUTHKIT_DOMAIN", "").strip() or None
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").strip() or None
USER_EMAIL_CACHE = Path.home() / ".config" / "teamster" / "cube-user-email"
META_CACHE_DIR = Path.home() / ".cache" / "teamster"
META_CACHE_TTL_SECONDS = 60 * 60
TIMEOUT_SECONDS = 55
TOKEN_TTL_SECONDS = 5 * 60
# All mart date columns are date-grain midnight-UTC; a non-UTC query timezone
# makes Cube's convertTz shift dates-join predicates and day-granularity
# results off by one day (#4298). Default queries to UTC unless the caller
# explicitly asks for another timezone.
DEFAULT_QUERY_TIMEZONE = "UTC"

# Deploy sets SERVER_SHA to the commit; stdio dev runs log "local".
SERVER_SHA = os.environ.get("SERVER_SHA", "").strip() or "local"
# Off unless the deploy sets "true". `question` and `assumptions` are free text
# staff type about students, and capturing them waits on People Operations
# sign-off (Refs #5613). `query_json` and `error_message` always log: they
# repeat values the warehouse already holds.
LOG_FREE_TEXT = os.environ.get("CUBE_MCP_LOG_FREE_TEXT", "").strip().lower() == "true"

TRANSPORT_STDIO = "stdio"
TRANSPORT_HTTP = "http"
VALID_TRANSPORTS = frozenset({TRANSPORT_STDIO, TRANSPORT_HTTP})


class UserEmailPrompt(BaseModel):
    email: str = Field(
        description=(
            "Your Google Workspace email "
            "(e.g. firstlast@apps.teamschools.org). Used as the JWT security "
            "context to resolve your cube-* group memberships."
        )
    )


class MissingUserEmailError(RuntimeError):
    """Raised when no email is available and the client can't be prompted."""


def _write_user_email(email: str) -> None:
    USER_EMAIL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    USER_EMAIL_CACHE.write_text(email + "\n", encoding="utf-8")


def _get_oauth_email() -> str:
    access_token = get_access_token()
    if isinstance(access_token, CubeAccessToken) and access_token.email:
        return access_token.email.strip()
    raise MissingUserEmailError(
        "cube MCP: OAuth bearer token missing or has no verified "
        "`email` claim. Check the WorkOS AuthKit JWT template."
    )


async def _get_local_email(ctx: Context) -> str:
    env_override = os.environ.get("CUBE_USER_EMAIL", "").strip()
    if env_override:
        return env_override
    if USER_EMAIL_CACHE.exists():
        cached = USER_EMAIL_CACHE.read_text(encoding="utf-8").strip()
        if cached:
            return cached
    supports_elicit = ctx.session.check_client_capability(
        ClientCapabilities(elicitation=ElicitationCapability())
    )
    if not supports_elicit:
        raise MissingUserEmailError(
            "cube MCP has no user email configured and this client does not "
            "support elicitation. Set the CUBE_USER_EMAIL environment "
            "variable before launching the server, or write the email to "
            f"{USER_EMAIL_CACHE} (one line, no trailing newline)."
        )
    result = await ctx.elicit(
        message=(
            "cube MCP needs your Google Workspace email to set the JWT "
            f"security context. Will be cached at {USER_EMAIL_CACHE} for "
            "future sessions."
        ),
        schema=UserEmailPrompt,
    )
    if result.action != "accept" or not result.data:
        raise MissingUserEmailError(
            "cube MCP: email required for security context. Set the "
            "CUBE_USER_EMAIL environment variable or write it to the cache file."
        )
    email = result.data.email.strip()
    _write_user_email(email)
    return email


async def _get_user_email(ctx: Context) -> str:
    if AUTHKIT_DOMAIN:
        return _get_oauth_email()
    return await _get_local_email(ctx)


_TOKEN_REFRESH_BUFFER_SECONDS = 30
_token_cache: dict[str, tuple[str, int]] = {}


def _mint_token(email: str) -> str:
    now = int(time.time())
    cached = _token_cache.get(email)
    if cached and cached[1] - now > _TOKEN_REFRESH_BUFFER_SECONDS:
        return cached[0]
    exp = now + TOKEN_TTL_SECONDS
    # `iat` is required by cube.js's `jwt.verify(..., { maxAge: "12h" })` —
    # PyJWT does not add it automatically. `exp` alone is not enough: maxAge
    # derives its cutoff from `iat`, not `exp`, so a token minted without it
    # would fail `checkAuth` with "iat required when maxAge is specified".
    token = jwt.encode(
        {"email": email, "iat": now, "exp": exp}, CUBE_API_SECRET, algorithm="HS256"
    )
    _token_cache[email] = (token, exp)
    return token


class CubeAccessToken(AccessToken):
    """AccessToken with the verified Workspace email attached."""

    email: str


class JWKSTokenVerifier:
    """Verifies AuthKit-issued JWTs against the WorkOS AuthKit JWKS."""

    def __init__(self, authkit_domain: str) -> None:
        self._issuer = f"https://{authkit_domain}"
        self._jwks_client = jwt.PyJWKClient(
            f"{self._issuer}/oauth2/jwks",
            cache_keys=True,
            max_cached_keys=16,
            lifespan=3600,
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                # aud not included in AuthKit access tokens by default;
                # token-to-resource binding is enforced via RFC 8707 resource
                # indicator configured in WorkOS Connect → Configuration.
                options={"verify_aud": False},
            )
        except jwt.PyJWTError:
            return None
        email = claims.get("email")
        if not isinstance(email, str) or not email:
            return None
        return CubeAccessToken(
            token=token,
            client_id=claims.get("sub", email),
            scopes=[],
            expires_at=claims.get("exp"),
            email=email,
        )


# mcp SDK 2.0 fixed the bug where stateless_http=True re-entered a `lifespan=`
# context manager on every HTTP request (streamable_http_manager now enters it
# once for the manager's lifetime and reuses that state across requests), so
# it's now safe to manage the httpx client's shutdown here instead of leaving
# it as a bare module-level global with no `aclose()`.
client: httpx.AsyncClient | None = None


@asynccontextmanager
async def _lifespan(_server: "MCPServer[None]") -> AsyncIterator[None]:
    global client
    client = httpx.AsyncClient(
        base_url=CUBE_REST_URL,
        headers={"Content-Type": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )
    try:
        yield
    finally:
        await client.aclose()
        client = None


_mcpserver_kwargs: dict[str, Any] = {}
if AUTHKIT_DOMAIN and PUBLIC_URL:
    _mcpserver_kwargs["token_verifier"] = JWKSTokenVerifier(AUTHKIT_DOMAIN)
    _mcpserver_kwargs["auth"] = AuthSettings(
        issuer_url=f"https://{AUTHKIT_DOMAIN}",  # type: ignore[arg-type]
        resource_server_url=PUBLIC_URL,  # type: ignore[arg-type]
    )

mcp = MCPServer(
    "cube",
    instructions=(
        "Query the Cube semantic layer (KIPP TEAM & Family metrics, dimensions, "
        "and views) via Cube Cloud's REST API. Start with the `meta` tool to "
        "discover views, then build a query and call `load` to execute (or "
        "`sql` to inspect the compiled SQL). The load-bearing query-construction "
        "guidance — member naming, filter operators, date handling, the "
        "academic-year convention, and PII handling — lives in the individual "
        "`meta`/`load`/`sql` tool descriptions, which reach the model reliably "
        "on every surface (unlike this instructions block, which some clients "
        "drop or truncate)."
    ),
    lifespan=_lifespan,
    **_mcpserver_kwargs,
)


async def _request(
    method: str,
    path: str,
    *,
    email: str,
    poll: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("_request called before the server lifespan started")
    call = _current_call.get()
    headers = {"Authorization": _mint_token(email)}
    if call is not None:
        # Cube stamps this onto the BigQuery job as the `cube_request_id`
        # label, which joins a call record to its job's cost and SQL.
        headers["x-request-id"] = call.cube_request_id
    deadline = time.monotonic() + TIMEOUT_SECONDS
    started = time.monotonic()
    try:
        while True:
            response = await client.request(method, path, headers=headers, **kwargs)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Cube {method} {path} {response.status_code}: {response.text}"
                )
            body = response.json()
            if poll and isinstance(body, dict) and body.get("error") == "Continue wait":
                if time.monotonic() + 1 >= deadline:
                    raise RuntimeError(
                        f"Cube {method} {path} did not complete within "
                        f"{TIMEOUT_SECONDS}s ('Continue wait' polling)"
                    )
                await asyncio.sleep(1)
                continue
            return body
    finally:
        if call is not None:
            call.latency_ms += (time.monotonic() - started) * 1000


def _with_default_timezone(query: dict[str, Any]) -> dict[str, Any]:
    """Return the query with timezone defaulted to UTC when the caller omits
    it, so a deployment-level CUBEJS_DEFAULT_TIMEZONE can't silently shift
    date-grain results (#4298). Caller-provided timezones pass through."""
    if query.get("timezone"):
        return query
    return {**query, "timezone": DEFAULT_QUERY_TIMEZONE}


# Call record: 1 JSON line per tool call, written to stderr for Cloud Logging.
# Design and the sink that routes it to BigQuery: Refs #5613.
CALL_RECORD_TEXT_LIMIT = 10_000


def _clip(text: str | None) -> str | None:
    """Cut a text field so 1 record stays far under Cloud Logging's 256 KB
    entry limit."""
    if text is None:
        return None
    return text[:CALL_RECORD_TEXT_LIMIT]


def _resolve_session_id(raw: str | None) -> tuple[str, bool]:
    """Return `(session_id, minted)`. A value that is not a UUID is replaced
    and never echoed, so free text a model passes here never reaches the log."""
    with contextlib.suppress(ValueError):
        return str(uuid.UUID((raw or "").strip())), False
    return str(uuid.uuid4()), True


def _filter_members(filters: Any) -> Iterator[str]:
    """Yield the member of every filter, walking nested `and`/`or` groups.
    Filter values are never read."""
    if not isinstance(filters, list):
        return
    for item in filters:
        if not isinstance(item, dict):
            continue
        for group in ("and", "or"):
            yield from _filter_members(item.get(group))
        member = item.get("member") or item.get("dimension")
        if isinstance(member, str):
            yield member


def _members_referenced(query: dict[str, Any]) -> list[str]:
    """Every member a Cube query names, sorted and unique. Names only."""
    members: set[str] = set()
    # Cube rejects a non-list member field, but its call still needs a record:
    # skip the field rather than iterate a string or raise on a number.
    for key in ("measures", "dimensions", "segments"):
        values = query.get(key)
        if isinstance(values, list):
            members.update(m for m in values if isinstance(m, str))
    time_dimensions = query.get("timeDimensions")
    for time_dimension in time_dimensions if isinstance(time_dimensions, list) else []:
        if isinstance(time_dimension, dict) and isinstance(
            time_dimension.get("dimension"), str
        ):
            members.add(time_dimension["dimension"])
    members.update(_filter_members(query.get("filters")))
    order = query.get("order")
    if isinstance(order, dict):
        members.update(k for k in order if isinstance(k, str))
    elif isinstance(order, list):
        members.update(
            pair[0]
            for pair in order
            if isinstance(pair, (list, tuple)) and pair and isinstance(pair[0], str)
        )
    return sorted(members)


def _views_referenced(members: list[str]) -> list[str]:
    return sorted({m.split(".", 1)[0] for m in members})


def _load_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Pull the pre-aggregation and size fields out of a `/v1/load` response.
    A multi-query response (`results`) is summarized across its parts: served
    by a pre-aggregation only if every part was, refreshed as of its stalest
    part. Rows are counted, never copied."""
    results = payload.get("results")
    parts = (
        [r for r in results if isinstance(r, dict)]
        if isinstance(results, list)
        else [payload]
    )
    externals = [p["external"] for p in parts if isinstance(p.get("external"), bool)]
    used: set[str] = set()
    for part in parts:
        entries = part.get("usedPreAggregations")
        if not isinstance(entries, dict):
            continue
        for table_name, info in entries.items():
            # The id is stable; the table name carries a hash that changes on
            # every rebuild.
            pre_aggregation_id = (
                info.get("preAggregationId") if isinstance(info, dict) else None
            )
            used.add(
                pre_aggregation_id
                if isinstance(pre_aggregation_id, str)
                else table_name
            )
    refresh_times = [
        p["lastRefreshTime"] for p in parts if isinstance(p.get("lastRefreshTime"), str)
    ]
    return {
        "external": all(externals) if externals else None,
        "used_pre_aggregations": sorted(used),
        "last_refresh_time": min(refresh_times) if refresh_times else None,
        "row_count": sum(
            len(p["data"]) for p in parts if isinstance(p.get("data"), list)
        ),
    }


CALL_RECORD_EVENT = "cube_mcp_call"
# The only keys a record may carry, in order. A test pins the logged keys to
# this tuple, so widening the payload is a deliberate edit here, matched in the
# dbt staging model's contract.
CALL_RECORD_FIELDS: tuple[str, ...] = (
    "cube_request_id",
    "ts",
    "tool",
    "session_id",
    "session_id_minted",
    "email",
    "client",
    "question",
    "question_provided",
    "assumptions",
    "query_json",
    "views_referenced",
    "members_referenced",
    "outcome",
    "error_message",
    "external",
    "used_pre_aggregations",
    "last_refresh_time",
    "row_count",
    "latency_ms",
    "server_sha",
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _client_user_agent(ctx: Context) -> str | None:
    """The calling client's User-Agent, or None on stdio or outside a request."""
    with contextlib.suppress(Exception):
        headers = ctx.headers
        value = headers.get("user-agent") if headers is not None else None
        if isinstance(value, str):
            return value
    return None


@dataclass
class _CallRecord:
    """What 1 tool call did. Never holds response rows: `result` is read for
    counts and pre-aggregation fields only, in `row()`."""

    tool: str
    session_id: str
    session_id_minted: bool
    question: str | None = None
    assumptions: str | None = None
    query: dict[str, Any] | None = None
    views: list[str] | None = None
    cube_request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=_utc_now)
    email: str | None = None
    client: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float = 0.0

    def row(self) -> dict[str, Any]:
        """The logged row. Empty arrays become null, because the BigQuery sink
        cannot type a column from an empty array."""
        members = _members_referenced(self.query) if self.query is not None else []
        views = (
            _views_referenced(members)
            if self.query is not None
            else sorted(self.views or [])
        )
        summary: dict[str, Any] = (
            _load_summary(self.result)
            if self.tool == "load" and self.result is not None
            else {}
        )
        if self.error is not None:
            outcome = "error"
        elif summary.get("row_count") == 0:
            outcome = "empty"
        else:
            outcome = "ok"
        row = {
            "cube_request_id": self.cube_request_id,
            "ts": self.ts,
            "tool": self.tool,
            "session_id": self.session_id,
            "session_id_minted": self.session_id_minted,
            "email": self.email,
            "client": _clip(self.client),
            "question": _clip(self.question) if LOG_FREE_TEXT else None,
            "question_provided": bool(self.question and self.question.strip()),
            "assumptions": _clip(self.assumptions) if LOG_FREE_TEXT else None,
            "query_json": (
                _clip(json.dumps(self.query, sort_keys=True, default=str))
                if self.query is not None
                else None
            ),
            "views_referenced": views or None,
            "members_referenced": members or None,
            "outcome": outcome,
            "error_message": _clip(self.error),
            "external": summary.get("external"),
            "used_pre_aggregations": summary.get("used_pre_aggregations") or None,
            "last_refresh_time": summary.get("last_refresh_time"),
            "row_count": summary.get("row_count"),
            "latency_ms": round(self.latency_ms),
            "server_sha": SERVER_SHA,
        }
        return {key: row[key] for key in CALL_RECORD_FIELDS}


def _emit_call_record(record: _CallRecord) -> None:
    """Write 1 record to stderr as a JSON line. Cloud Run ships it to Cloud
    Logging as `jsonPayload`; stdout is the MCP transport in stdio mode. Cloud
    Run moves `severity` onto the log entry itself. A failure here never
    reaches the tool's caller."""
    with contextlib.suppress(Exception):
        line = {"event": CALL_RECORD_EVENT, "severity": "INFO", **record.row()}
        print(json.dumps(line, default=str), file=sys.stderr, flush=True)


# The record of the tool call in progress, so `_request` can tag Cube requests
# with its id and add its latency without threading it through every helper.
_current_call: ContextVar[_CallRecord | None] = ContextVar(
    "_current_call", default=None
)


@asynccontextmanager
async def _recorded(
    ctx: Context,
    tool: str,
    *,
    session_id: str | None,
    question: str | None = None,
    assumptions: str | None = None,
    query: dict[str, Any] | None = None,
    views: list[str] | None = None,
) -> AsyncGenerator[_CallRecord]:
    """Record 1 tool call: yield its `_CallRecord`, then write it on the way
    out, success or failure. An exception is noted and re-raised unchanged."""
    resolved_session_id, minted = _resolve_session_id(session_id)
    record = _CallRecord(
        tool=tool,
        session_id=resolved_session_id,
        session_id_minted=minted,
        question=question,
        assumptions=assumptions,
        query=query,
        views=views,
        client=_client_user_agent(ctx),
    )
    token = _current_call.set(record)
    try:
        yield record
    except BaseException as exc:
        # A client disconnect or client-side timeout cancels the call with a
        # message that embeds a memory address; a fixed one keeps it countable.
        if isinstance(exc, asyncio.CancelledError):
            record.error = "cancelled"
        else:
            record.error = str(exc) or type(exc).__name__
        raise
    finally:
        _current_call.reset(token)
        _emit_call_record(record)


def _meta_scope_key(views: list[str] | None) -> str:
    """Distinguish a filtered fetch from the full `/meta` catalog in the cache
    key — a filtered call must never read or write the full catalog's cache
    entry, or another view-set's."""
    if not views:
        return "all"
    return "views:" + ",".join(sorted(views))


def _meta_cache_path(email: str, scope: str) -> Path:
    digest = hashlib.sha256(f"{email}:{scope}".encode("utf-8")).hexdigest()[:16]
    return META_CACHE_DIR / f"cube-meta-{digest}.json"


_meta_memory_cache: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}


def _read_meta_cache(
    email: str, scope: str, force_refresh: bool
) -> dict[str, Any] | None:
    """Return a cached payload for (email, scope) if fresh, else None. Checks
    the in-memory cache first, then falls back to disk (surviving process
    restarts) — writing back through the disk hit to warm the memory cache."""
    now = int(time.time())
    if not force_refresh:
        memory_hit = _meta_memory_cache.get((email, scope))
        if memory_hit and memory_hit[0] > now:
            return memory_hit[1]
    cache_path = _meta_cache_path(email, scope)
    if not force_refresh and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            expires_at = int(cached.get("expires_at", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            # Corrupt cache file — drop it so subsequent runs don't keep failing.
            cache_path.unlink(missing_ok=True)
        else:
            if expires_at > now and "payload" in cached:
                _meta_memory_cache[(email, scope)] = (expires_at, cached["payload"])
                return cached["payload"]
    return None


def _write_meta_cache(email: str, scope: str, payload: dict[str, Any]) -> None:
    expires_at = int(time.time()) + META_CACHE_TTL_SECONDS
    _meta_memory_cache[(email, scope)] = (expires_at, payload)
    cache_path = _meta_cache_path(email, scope)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: avoid corruption if two concurrent meta() calls race.
    tmp_path = cache_path.with_suffix(f".tmp.{os.getpid()}")
    tmp_path.write_text(
        json.dumps({"expires_at": expires_at, "payload": payload}),
        encoding="utf-8",
    )
    os.replace(tmp_path, cache_path)


async def _fetch_full_meta(email: str, force_refresh: bool) -> dict[str, Any]:
    """Fetch (or serve from cache) the full `/meta` catalog for `email`. A
    private helper — not the `meta` tool itself — so the filtered-view path
    below can reuse it without resolving the caller's email or hitting
    `/meta` twice."""
    cached = _read_meta_cache(email, "all", force_refresh)
    if cached is not None:
        return cached
    payload = await _request("GET", "/meta", email=email)
    _write_meta_cache(email, "all", payload)
    return payload


async def _meta_payload(
    email: str, views: list[str] | None, force_refresh: bool
) -> dict[str, Any]:
    """The `meta` catalog for `email`, filtered to `views` when given, served
    from cache when fresh."""
    scope = _meta_scope_key(views)
    if scope == "all":
        return await _fetch_full_meta(email, force_refresh)

    cached = _read_meta_cache(email, scope, force_refresh)
    if cached is not None:
        return cached
    full_payload = await _fetch_full_meta(email, force_refresh)
    wanted = set(views or [])
    payload = {
        **full_payload,
        "cubes": [
            dict(c) for c in full_payload.get("cubes", []) if c.get("name") in wanted
        ],
    }
    _write_meta_cache(email, scope, payload)
    return payload


@mcp.tool()
async def meta(
    ctx: Context,
    views: list[str] | None = None,
    force_refresh: bool = False,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Discover available KIPP TEAM & Family data: students, attendance, grades,
    assessments, enrollment, demographics, staff, schools, regions, terms.
    Returns the catalog of views, measures, and dimensions queryable via `load`
    or `sql`.

    Call with no arguments first to discover which views exist — analyst-facing
    surfaces are views (e.g. `student_attendance_enrollment_daily_view`,
    `student_attendance_enrollment_periods_view`, `student_assessment_scores_view`; staff
    is split into `staff_directory` and `staff_pii` by access tier). Once you
    know the view(s) you need, pass
    `views` to get back just their measures and dimensions — a fraction of the
    full catalog's size, filtered client-side from the same underlying `/meta`
    fetch (Cube's REST API doesn't take a filter param, and its separate
    `/entities` endpoints need a differently scoped token this server doesn't
    mint) — so it avoids exceeding a response size budget on large models
    without any extra round trip once the full catalog is cached.

    Two views can cover one domain at different grains. Attendance splits this
    way: `student_attendance_enrollment_daily_view` answers day-level questions (was a student
    absent on a date, calendar heatmaps, day-of-week patterns), while
    `student_attendance_enrollment_periods_view` answers rates as of a period (chronic
    absence, ADA tier, truancy) via its `period_type` dimension. Pick by whether
    the question is about a day or about a period, and do not add an anchor
    filter to either — neither view needs one.

    Enrollment lives on those same two views — there is no separate
    enrollment view. `student_attendance_enrollment_daily_view.count_students` counts distinct students
    over whatever slice is queried, so it answers ever-enrolled over a range and
    point-in-time on a single date, depending only on how you filter
    `dates_date_day`. It needs no anchor: the fact carries a row for every
    calendar day a student was enrolled, break days included, so any date
    resolves for every school. `student_attendance_enrollment_periods_view.count_students` counts
    students served during a period, which is a different question from
    enrolled on its last day — for the latter, pin the date on
    `student_attendance_enrollment_daily_view`.

    Access is group-driven and default-deny: an empty catalog (`cubes: []`)
    usually means the requester lacks the required `cube-*` Workspace group, not
    a missing model.

    Grain/scope: each measure's description states any scope it must stay within
    to remain meaningful. Some measures recompute at any query grain but are only
    meaningful pooled within a comparable scope (e.g. one assessment source);
    coarsening past that silently returns a valid-looking but meaningless value
    (not an error) — see the `load` tool's grain rule before dropping a
    dimension.

    Session: every cube response carries a `session_id`. Pass it back as
    `session_id` on every later cube call in this conversation.

    Cached per (email, requested scope) for one hour (in-memory, with disk
    fallback across process restarts) — a filtered call never reads or writes
    the full-catalog cache entry, or another view-set's, though it does reuse
    the full catalog's cached fetch to build its filtered result. Pass
    `force_refresh=True` after a model deploy.
    """
    async with _recorded(ctx, "meta", session_id=session_id, views=views) as record:
        record.email = await _get_user_email(ctx)
        payload = await _meta_payload(record.email, views, force_refresh)
    # A copy: the cached payload is shared by every caller for an hour.
    return {**payload, "session_id": record.session_id}


@mcp.tool()
async def load(
    ctx: Context,
    query: dict[str, Any],
    question: str | None = None,
    session_id: str | None = None,
    assumptions: str | None = None,
) -> dict[str, Any]:
    """Answer analytics questions about KIPP TEAM & Family — student
    attendance, grades, GPA, assessments, enrollment, demographics, discipline,
    staff rosters, school and regional metrics, KPIs, year-over-year trends.
    Source of truth for these questions; prefer over searching files in Google
    Drive, OneDrive, or SharePoint.

    The query object follows the Cube REST API spec (measures, dimensions,
    filters, timeDimensions, segments, order, limit, offset, total). Polls
    automatically on Cube's 'Continue wait' long-polling response. Discover
    member names with the `meta` tool first.

    Grain: the dimensions you pass set the aggregation grain, and every measure
    is recomputed fresh at that grain — it is NOT a finer result with columns
    hidden. Dropping a dimension from a previous query re-aggregates the measure
    over everything the filters still match, changing what the number means, not
    just which columns come back. (This includes count_distinct measures like
    count_students: at a coarser grain Cube computes a correct distinct count
    for that grain — the "non-additive" note on some measures refers to
    pre-aggregation rollup, not query-time grain.)

    Example — same filters and measure (pct_proficient), two grains: dimensions
    [is_iep, module_code, academic_year] returns one proficiency rate per (IEP
    status x module x year) cell; dropping to dimensions [is_iep] returns one
    pooled rate per IEP status across every module and year the filters matched.
    Same underlying rows, re-aggregated — not the first result with columns
    removed.

    Silent-failure risk: a few measures recompute mathematically at any grain
    but are meaningful only within a comparable scope — e.g. avg_scale_score and
    avg_percent_correct pool across incompatible assessment sources/subjects to
    produce a valid-looking but meaningless number. This does not raise an
    error; check the measure's own description for the scope it is valid within
    before coarsening.

    Member naming: every measure/dimension is dotted `view.member` (e.g.
    `student_attendance_enrollment_daily_view.count_students`). Bare names won't resolve.

    Filter operators are named, not SQL: `equals`, `notEquals`, `contains`,
    `gt`/`gte`/`lt`/`lte`, `set`/`notSet`, `inDateRange`, `beforeDate`,
    `afterDate`. SQL-style `=`/`IN`/`LIKE` won't parse.

    Date dimensions: for a single date use `filters` with `equals`; for a range
    or when you need `granularity` (day/week/month/etc.), use `timeDimensions`
    with `dateRange`. Putting a date in the wrong place either fails or silently
    drops the granularity.

    Academic year: an academic_year value of 2025 means the 2025-26 school year
    (July 2025 - June 2026), not the year ending in 2025 — the opposite of
    fiscal-year convention. When a user says 'this year'/'current year', use the
    academic_year whose start year matches the current calendar year (e.g. in
    May 2026, current academic_year = 2025). Exposed as `dates_academic_year`
    (integer) and `dates_academic_year_label` (string, e.g. '2025-2026').

    ACADEMIC YEAR — resolve it yourself before building any query that names a
    year:
    - academic_year is the START year; 'SY' notation uses the END year.
    - 'SY26' -> academic_year 2025, label '2025-2026' (SY end year minus 1).
    - '2025-26', '2025-2026', 'AY2025' -> academic_year 2025, label '2025-2026'.
    - bare '2026' -> treat as the START year (academic_year 2026, label
      '2026-2027'); if the user's wording implies SY / end-year, note the other
      reading.
    State your interpretation inline (e.g. 'Interpreting as the 2025-2026 school
    year') before showing results, then proceed.

    Numeric values come back as strings — cast to numeric before comparing or
    doing arithmetic. Raw `==`/`<` compare lexicographically (`'10' < '9'`).

    PII: student view results carry row-level student identifiers alongside
    aggregate-safe dimensions — avoid pulling identifier fields (student_key,
    full_name, birth_date, state/lea IDs) unless drill-down is explicitly
    requested. Staff sensitive fields (personal contact, birth date,
    demographics) live in `staff_pii`, gated separately from the open
    `staff_directory` roster. Keep any identifying values — student or staff —
    in the local conversation only, never to PR comments, issues, Slack, or
    scheduled-agent outputs.

    Queries default to timezone UTC (mart dates are date-grain UTC); pass an
    explicit `timezone` only when wall-clock conversion is intended.

    Every call is recorded for the data team, never with the result rows. Pass
    `question`: the person's question, verbatim, and the same text on every
    call made for it. If an earlier cube response in this conversation gave you
    a `session_id`, pass it. Pass `assumptions`: the interpretive choices you
    made turning the question into this query.
    """
    sent = _with_default_timezone(query)
    async with _recorded(
        ctx,
        "load",
        session_id=session_id,
        question=question,
        assumptions=assumptions,
        query=sent,
    ) as record:
        record.email = await _get_user_email(ctx)
        result = await _request(
            "POST", "/load", json={"query": sent}, email=record.email, poll=True
        )
        record.result = result
    return {**result, "session_id": record.session_id}


@mcp.tool()
async def sql(
    ctx: Context,
    query: dict[str, Any],
    question: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Inspect the BigQuery SQL Cube would generate for a KIPP TEAM & Family
    analytics query, without running it. Useful for debugging query shape,
    verifying access policies, or reviewing the compiled SQL before `load`.

    Takes the same query object as `load` — see the `load` tool description for
    member naming, filter operators, date handling, and the academic-year
    convention.

    Response is wrapped: {"sql": {"status", "sql": [query-string, [params]], "query_type"}}.
    A default-deny access result compiles to `WHERE (1 = 0)` plus
    `rlsAccessDenied` — usually a missing `cube-*` Workspace group, not a schema
    bug.

    Queries default to timezone UTC (mart dates are date-grain UTC); pass an
    explicit `timezone` only when wall-clock conversion is intended.

    Every call is recorded for the data team. Pass `question`: the person's
    question, verbatim, and the same text on every call made for it. If an
    earlier cube response in this conversation gave you a `session_id`, pass
    it.
    """
    sent = _with_default_timezone(query)
    async with _recorded(
        ctx, "sql", session_id=session_id, question=question, query=sent
    ) as record:
        record.email = await _get_user_email(ctx)
        result = await _request(
            "GET", "/sql", params={"query": json.dumps(sent)}, email=record.email
        )
    return {**result, "session_id": record.session_id}


def main() -> None:
    transport = os.environ.get("TRANSPORT", TRANSPORT_STDIO)
    if transport not in VALID_TRANSPORTS:
        raise RuntimeError(
            f"TRANSPORT must be one of {sorted(VALID_TRANSPORTS)}, got {transport!r}"
        )
    if transport == TRANSPORT_HTTP:
        if AUTHKIT_DOMAIN and not PUBLIC_URL:
            raise RuntimeError(
                "AUTHKIT_DOMAIN is set but PUBLIC_URL is not — the Cloud "
                "Run service URL is required for OAuth resource-server "
                "metadata in HTTP mode."
            )
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",  # trunk-ignore(bandit/B104): intentional for Cloud Run
            port=8080,
            # stateless_http lets Cloud Run scale horizontally — no per-instance
            # session state, every request stands alone. We don't use MCP
            # features that require persistent sessions (subscriptions,
            # server-initiated messages); elicit is only invoked in stdio dev
            # mode.
            stateless_http=True,
        )
    else:
        mcp.run()


if __name__ == "__main__":
    main()
