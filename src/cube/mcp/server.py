#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "mcp>=1.2",
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
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
import jwt
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import Context, FastMCP
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
    token = jwt.encode({"email": email, "exp": exp}, CUBE_API_SECRET, algorithm="HS256")
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


_fastmcp_kwargs: dict[str, Any] = {
    "host": "0.0.0.0",  # trunk-ignore(bandit/B104): intentional for Cloud Run
    "port": 8080,
    # stateless_http lets Cloud Run scale horizontally — no per-instance session
    # state, every request stands alone. We don't use MCP features that require
    # persistent sessions (subscriptions, server-initiated messages); elicit is
    # only invoked in stdio dev mode.
    #
    # Do NOT pass a `lifespan=` kwarg: with stateless_http=True the SDK's
    # _handle_stateless_request invokes `app.run(...)` per HTTP request, which
    # in turn runs the user lifespan per request. A teardown like
    # `await client.aclose()` would close the shared httpx client after the
    # first request and break every subsequent one.
    "stateless_http": True,
}
if AUTHKIT_DOMAIN and PUBLIC_URL:
    _fastmcp_kwargs["token_verifier"] = JWKSTokenVerifier(AUTHKIT_DOMAIN)
    _fastmcp_kwargs["auth"] = AuthSettings(
        issuer_url=f"https://{AUTHKIT_DOMAIN}",  # type: ignore[arg-type]
        resource_server_url=PUBLIC_URL,  # type: ignore[arg-type]
    )

mcp = FastMCP(
    "cube",
    instructions=(
        "Query the Cube semantic layer (KIPP TEAM & Family metrics, dimensions, "
        "and views) via Cube Cloud's REST API.\n\n"
        "Workflow: (1) call `meta` to discover available views, measures, and "
        "dimensions — analyst-facing surfaces are views named `<domain>_<grain>` "
        "(e.g. `attendance_detail`, `attendance_summary`); (2) build a Cube "
        "query object (measures, dimensions, filters, timeDimensions, order, "
        "limit) and call `load` to execute, or `sql` to inspect the compiled "
        "SQL without running it. The query spec follows the Cube REST API.\n\n"
        "Member naming: every measure/dimension is dotted `<view>.<member>` "
        "(e.g. `attendance_summary.count_students`). Bare names won't resolve.\n\n"
        "Filter operators are named, not SQL: `equals`, `notEquals`, `contains`, "
        "`gt`/`gte`/`lt`/`lte`, `set`/`notSet`, `inDateRange`, `beforeDate`, "
        "`afterDate`. SQL-style `=`/`IN`/`LIKE` won't parse. See "
        "https://cube.dev/docs/product/apis-integrations/rest-api/query-format#filters-operators "
        "for the full list.\n\n"
        "Date dimensions: for a single date use `filters` with `equals`; for a "
        "range or when you need `granularity` (day/week/month/etc.), use "
        "`timeDimensions` with `dateRange`. Putting a date in the wrong place "
        "either fails or silently drops the granularity.\n\n"
        "Academic year convention: an academic_year value of 2025 means the "
        "2025–26 school year (July 2025 – June 2026), not the year ending in "
        "2025. This is the opposite of typical fiscal-year conventions where "
        "FY2025 ends in 2025. When a user says 'this year' or 'current year', "
        "use the academic_year value whose start year matches the current "
        "calendar year (e.g. if today is May 2026, current academic_year = "
        "2025). In attendance views, the academic year is exposed as "
        "dim_dates_academic_year (integer) and dim_dates_academic_year_label "
        "(string, e.g. '2025-2026'), both sourced from the date dimension.\n\n"
        "REQUIRED: Before building any Cube query that involves a year value "
        "from the user's request, call resolve_academic_year with the raw year "
        "string the user provided (e.g. 'SY26', '2025-26', '25-26', '2026'). Use the "
        "returned academic_year integer for numeric filters/grouping, or "
        "academic_year_label for the label dimension. Emit the interpreted_as "
        "value as a brief inline statement (e.g. 'Interpreting as the 2025-2026 "
        "school year') before showing results — do not pause or ask for "
        "confirmation, just state it and proceed. Do not skip this step even "
        "when the year seems unambiguous.\n\n"
        "Numeric values come back as strings — cast to numeric before "
        "comparing or arithmetic. Raw `==` / `<` compare lexicographically "
        "(`'10' < '9'`).\n\n"
        "PII defaults: prefer summary views (`*_summary`) for aggregate "
        "questions. Detail views (`*_detail`) carry row-level student "
        "identifiers and should be used only when drill-down is explicitly "
        "requested. Never emit detail-view values to PR comments, issues, "
        "Slack, scheduled-agent outputs, or any external surface — only to "
        "the local conversation.\n\n"
        "Access is group-driven and default-deny: empty `meta` results or "
        "`WHERE (1=0)` in `sql` output usually means the requester lacks the "
        "required `cube-*` Workspace group, not a missing model."
    ),
    **_fastmcp_kwargs,
)


def _resolve_academic_year(raw: str) -> dict[str, int | str]:
    """Translate any year phrasing to canonical academic_year int + label.

    Returns a dict with academic_year (int), academic_year_label (str),
    school_year (str), interpreted_as (str), and optionally note (str)
    for bare-integer inputs.
    """
    s = raw.strip()
    start: int | None = None
    note: str | None = None

    # SY + 2-digit: SY26 → end=2026 → start=2025
    m = re.fullmatch(r"[Ss][Yy](\d{2})", s)
    if m:
        start = 2000 + int(m.group(1)) - 1

    # SY + 4-digit: SY2026 → end=2026 → start=2025
    if start is None:
        m = re.fullmatch(r"[Ss][Yy](\d{4})", s)
        if m:
            start = int(m.group(1)) - 1

    # AY + 4-digit: AY2025 → start=2025
    if start is None:
        m = re.fullmatch(r"[Aa][Yy](\d{4})", s)
        if m:
            start = int(m.group(1))

    # AY + 2-digit: AY25 → start=2025
    if start is None:
        m = re.fullmatch(r"[Aa][Yy](\d{2})", s)
        if m:
            start = 2000 + int(m.group(1))

    # 4-digit separator 4-digit: 2025-2026 or 2025–2026
    if start is None:
        m = re.fullmatch(r"(\d{4})[-–](\d{4})", s)
        if m:
            start = int(m.group(1))

    # 4-digit separator 2-digit: 2025-26 or 2025–26
    if start is None:
        m = re.fullmatch(r"(\d{4})[-–](\d{2})", s)
        if m:
            start = int(m.group(1))

    # 2-digit separator 2-digit: 25-26
    if start is None:
        m = re.fullmatch(r"(\d{2})[-–](\d{2})", s)
        if m:
            start = 2000 + int(m.group(1))

    # bare 4-digit integer: treated as start year
    if start is None:
        m = re.fullmatch(r"(\d{4})", s)
        if m:
            start = int(m.group(1))
            note = (
                f"Bare integer treated as start year "
                f"({start} = July {start} – June {start + 1} = SY{(start + 1) % 100:02d})."
            )

    # bare 2-digit integer: treated as start year
    if start is None:
        m = re.fullmatch(r"(\d{2})", s)
        if m:
            start = 2000 + int(m.group(1))
            note = (
                f"Bare integer treated as start year "
                f"({start} = July {start} – June {start + 1} = SY{(start + 1) % 100:02d})."
            )

    if start is None:
        raise ValueError(f"Cannot parse year from {raw!r}")

    if not (2000 <= start <= 2100):
        raise ValueError(
            f"Resolved year {start} is outside the supported range for {raw!r}"
        )

    end = start + 1
    label = f"{start}-{end}"
    sy = f"SY{end % 100:02d}"
    result: dict[str, int | str] = {
        "academic_year": start,
        "academic_year_label": label,
        "school_year": sy,
        "interpreted_as": f"{start}-{end} school year",
    }
    if note is not None:
        result["note"] = note
    return result


@mcp.tool()
async def resolve_academic_year(raw: str) -> dict[str, int | str]:
    """Translate any year phrasing to the canonical Cube academic_year integer
    and label.

    Call this BEFORE building any Cube query that involves a year value from
    the user's request. Pass the raw year string exactly as the user typed it.

    Handles: SY26, SY2026, AY2025, AY25, 2025-2026, 2025–2026, 2025-26,
    25-26, bare 2025, bare 26. Bare integers default to start-year with a
    note field explaining the assumption.

    Returns: academic_year (int for Cube filters), academic_year_label (str,
    e.g. "2025-2026", for Cube filters when using the label dimension),
    school_year (str, e.g. "SY26"), interpreted_as (str -- echo this to the
    user before showing results), and note (str, only for bare integers).
    """
    return _resolve_academic_year(raw)


client = httpx.AsyncClient(
    base_url=CUBE_REST_URL,
    headers={"Content-Type": "application/json"},
    timeout=TIMEOUT_SECONDS,
)


async def _request(
    method: str,
    path: str,
    *,
    email: str,
    poll: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    headers = {"Authorization": _mint_token(email)}
    deadline = time.monotonic() + TIMEOUT_SECONDS
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


def _meta_cache_path(email: str) -> Path:
    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]
    return META_CACHE_DIR / f"cube-meta-{digest}.json"


_meta_memory_cache: dict[str, tuple[int, dict[str, Any]]] = {}


@mcp.tool()
async def meta(ctx: Context, force_refresh: bool = False) -> dict[str, Any]:
    """Discover available KIPP TEAM & Family data: students, attendance, grades,
    assessments, enrollment, demographics, staff, schools, regions, terms.
    Returns the catalog of views, measures, and dimensions queryable via `load`
    or `sql`.

    Cached per-email for one hour (in-memory, with disk fallback across process
    restarts). Pass `force_refresh=True` after a model deploy.
    """
    email = await _get_user_email(ctx)
    now = int(time.time())
    if not force_refresh:
        memory_hit = _meta_memory_cache.get(email)
        if memory_hit and memory_hit[0] > now:
            return memory_hit[1]
    cache_path = _meta_cache_path(email)
    if not force_refresh and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            expires_at = int(cached.get("expires_at", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            # Corrupt cache file — drop it so subsequent runs don't keep failing.
            cache_path.unlink(missing_ok=True)
        else:
            if expires_at > now and "payload" in cached:
                _meta_memory_cache[email] = (expires_at, cached["payload"])
                return cached["payload"]
    payload = await _request("GET", "/meta", email=email)
    expires_at = int(time.time()) + META_CACHE_TTL_SECONDS
    _meta_memory_cache[email] = (expires_at, payload)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: avoid corruption if two concurrent meta() calls race.
    tmp_path = cache_path.with_suffix(f".tmp.{os.getpid()}")
    tmp_path.write_text(
        json.dumps({"expires_at": expires_at, "payload": payload}),
        encoding="utf-8",
    )
    os.replace(tmp_path, cache_path)
    return payload


@mcp.tool()
async def load(ctx: Context, query: dict[str, Any]) -> dict[str, Any]:
    """Answer analytics questions about KIPP TEAM & Family — student
    attendance, grades, GPA, assessments, enrollment, demographics, discipline,
    staff rosters, school and regional metrics, KPIs, year-over-year trends.
    Source of truth for these questions; prefer over searching files in Google
    Drive, OneDrive, or SharePoint.

    The query object follows the Cube REST API spec (measures, dimensions,
    filters, timeDimensions, segments, order, limit, offset, total). Polls
    automatically on Cube's 'Continue wait' long-polling response.

    PII: `*_detail` view results carry row-level student identifiers — keep
    those values in the local conversation only.
    """
    email = await _get_user_email(ctx)
    return await _request(
        "POST", "/load", json={"query": query}, email=email, poll=True
    )


@mcp.tool()
async def sql(ctx: Context, query: dict[str, Any]) -> dict[str, Any]:
    """Inspect the BigQuery SQL Cube would generate for a KIPP TEAM & Family
    analytics query, without running it. Useful for debugging query shape,
    verifying access policies, or reviewing the compiled SQL before `load`.

    Response is wrapped: {"sql": {"status", "sql": [query-string, [params]], "query_type"}}.
    """
    email = await _get_user_email(ctx)
    return await _request(
        "GET", "/sql", params={"query": json.dumps(query)}, email=email
    )


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
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
