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

Tools:
  meta - return the Cube data model catalog (cubes, views, dimensions, measures)
  load - run a Cube query (JSON body per the REST API spec)
  sql  - return the SQL Cube would generate for a query, without executing
"""

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import jwt
from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

CUBE_REST_URL = os.environ["CUBE_REST_URL"].rstrip("/")
CUBE_API_SECRET = os.environ["CUBE_API_SECRET"]
USER_EMAIL_CACHE = Path.home() / ".config" / "teamster" / "cube-user-email"
TIMEOUT_SECONDS = 60
TOKEN_TTL_SECONDS = 24 * 60 * 60
CONTINUE_WAIT_MAX_RETRIES = 30
CONTINUE_WAIT_SLEEP_SECONDS = 1.0


class UserEmailPrompt(BaseModel):
    email: str = Field(
        description=(
            "Your Google Workspace email "
            "(e.g. firstlast@apps.teamschools.org). Used as the JWT security "
            "context to resolve your cube-* group memberships."
        )
    )


async def _get_user_email(ctx: Context) -> str:
    env_override = os.environ.get("CUBE_USER_EMAIL", "").strip()
    if env_override:
        return env_override
    if USER_EMAIL_CACHE.exists():
        cached = USER_EMAIL_CACHE.read_text(encoding="utf-8").strip()
        if cached:
            return cached
    result = await ctx.elicit(
        message=(
            "cube-rest needs your Google Workspace email to set the JWT "
            f"security context. Will be cached at {USER_EMAIL_CACHE} for "
            "future sessions."
        ),
        schema=UserEmailPrompt,
    )
    if result.action != "accept" or not result.data:
        raise RuntimeError("cube-rest: email required for security context")
    email = result.data.email.strip()
    USER_EMAIL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    USER_EMAIL_CACHE.write_text(email + "\n", encoding="utf-8")
    return email


def _mint_token(email: str) -> str:
    payload = {
        "email": email,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, CUBE_API_SECRET, algorithm="HS256")


mcp = FastMCP(
    "cube-rest",
    instructions=(
        "Query the Cube semantic layer (KIPP TEAM & Family metrics, dimensions, "
        "and views) via Cube Cloud's REST API. Prefer this server over "
        "cube-mcp-server for analytics questions: it is deterministic and "
        "inspectable, with no LLM-in-the-loop SQL generation.\n\n"
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
        "`afterDate`, etc. SQL-style `=`/`IN`/`LIKE` won't parse.\n\n"
        "Date dimensions: for a single date use `filters` with `equals`; for a "
        "range or when you need `granularity` (day/week/month/etc.), use "
        "`timeDimensions` with `dateRange`. Putting a date in the wrong place "
        "either fails or silently drops the granularity.\n\n"
        "Numeric values come back as strings (precision preservation) — cast "
        "before comparing or doing math.\n\n"
        "PII defaults: prefer summary views (`*_summary`) for aggregate "
        "questions. Detail views (`*_detail`) carry row-level student "
        "identifiers and should be used only when drill-down is explicitly "
        "requested. Treat values from detail views per the project FERPA "
        "guidance — never emit them to external surfaces.\n\n"
        "Access is group-driven and default-deny: empty `meta` results or "
        "`WHERE (1=0)` in `sql` output usually means the requester lacks the "
        "required `cube-*` Workspace group, not a missing model."
    ),
)
client = httpx.Client(
    base_url=CUBE_REST_URL,
    headers={"Content-Type": "application/json"},
    timeout=TIMEOUT_SECONDS,
)


def _request(
    method: str,
    path: str,
    *,
    email: str,
    poll: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    headers = {"Authorization": _mint_token(email)}
    for _ in range(CONTINUE_WAIT_MAX_RETRIES if poll else 1):
        response = client.request(method, path, headers=headers, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Cube {method} {path} {response.status_code}: {response.text}"
            )
        body = response.json()
        if poll and isinstance(body, dict) and body.get("error") == "Continue wait":
            time.sleep(CONTINUE_WAIT_SLEEP_SECONDS)
            continue
        return body
    raise RuntimeError(
        f"Cube {method} {path} did not complete after "
        f"{CONTINUE_WAIT_MAX_RETRIES} 'Continue wait' polls"
    )


@mcp.tool()
async def meta(ctx: Context) -> dict[str, Any]:
    """Return the Cube data model catalog (cubes, views, dimensions, measures)."""
    email = await _get_user_email(ctx)
    return _request("GET", "/meta", email=email)


@mcp.tool()
async def load(query: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Run a Cube query against the REST API.

    The query object follows the Cube REST API spec. Common fields:
      measures, dimensions, filters, timeDimensions, segments,
      order, limit, offset, total

    Polls automatically on Cube's 'Continue wait' long-polling response.
    """
    email = await _get_user_email(ctx)
    return _request("POST", "/load", json={"query": query}, email=email, poll=True)


@mcp.tool()
async def sql(query: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Return the SQL Cube would generate for a query, without executing it.

    Response is wrapped: {"sql": {"status", "sql": [query-string, [params]], "query_type"}}.
    """
    email = await _get_user_email(ctx)
    return _request("GET", "/sql", params={"query": json.dumps(query)}, email=email)


if __name__ == "__main__":
    mcp.run()
