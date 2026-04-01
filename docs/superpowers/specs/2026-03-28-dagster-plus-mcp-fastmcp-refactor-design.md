# Refactor dagster_plus MCP Server to FastMCP

**Date:** 2026-03-28 **Status:** Approved **Scope:** `mcp/dagster_plus.py` →
`mcp/dagster_plus/` package

## Problem

`mcp/dagster_plus.py` is a 1250-line single file using the low-level MCP Server
API. Three separate locations must be updated to add or modify a tool:

1. GraphQL query string (~550 lines total)
2. `list_tools()` return with manual `inputSchema` dict (~420 lines)
3. `call_tool()` if/elif dispatch branch (~250 lines)

The manual JSON schema dicts and dispatch chain are repetitive and error-prone.

## Solution

Migrate to FastMCP (shipped with the MCP SDK v1.26.0) and split into a
multi-file package. FastMCP auto-generates JSON schemas from type hints and
handles tool dispatch internally, eliminating the `list_tools()` and
`call_tool()` boilerplate.

## Package Layout

```text
mcp/dagster_plus/
├── __init__.py          # empty
├── __main__.py          # entry point: imports tools, runs server
├── server.py            # FastMCP instance + gql() helper + env vars
├── queries.py           # 13 GraphQL query strings (moved as-is)
└── tools.py             # 15 @server.tool() decorated handlers
```

## Module Specifications

### `server.py`

- `FastMCP("dagster-plus")` instance
- Environment variable reads: `DAGSTER_CLOUD_API_TOKEN`,
  `DAGSTER_CLOUD_ORGANIZATION_ID` (default `"kipptaf"`),
  `DAGSTER_CLOUD_DEPLOYMENT` (default `"prod"`)
- `GRAPHQL_URL` constructed from env vars
- `gql(query, variables)` helper — unchanged logic: `httpx.Client` POST with 60s
  timeout, error handling for HTTP failures and GraphQL errors

### `queries.py`

All 13 GraphQL query string constants, moved verbatim:

- `LIST_RUNS_QUERY`
- `RUN_BY_ID_QUERY`
- `RUN_LOGS_QUERY`
- `COMPUTE_LOGS_QUERY`
- `CAPTURED_LOGS_METADATA_QUERY`
- `DAEMON_HEALTH_QUERY`
- `STALE_ASSETS_QUERY`
- `ASSET_MATERIALIZATIONS_QUERY`
- `ASSET_PARTITION_STATUSES_QUERY`
- `ASSET_CHECK_EXECUTIONS_QUERY`
- `ASSET_CONDITION_EVALUATIONS_QUERY`
- `TICK_HISTORY_QUERY`
- `CODE_LOCATIONS_QUERY`
- `BACKFILLS_QUERY`
- `BACKFILL_QUERY`

### `tools.py`

15 tool functions, each decorated with `@server.tool()`. Pattern:

```python
from typing import Annotated, Literal
from pydantic import Field

from .server import gql, server
from .queries import LIST_RUNS_QUERY

@server.tool()
async def list_runs(
    limit: Annotated[
        int, Field(description="Max runs to return (default 20, max 100).")
    ] = 20,
    cursor: Annotated[
        str | None, Field(description="Pagination cursor from a previous call.")
    ] = None,
    job_name: Annotated[
        str | None, Field(description="Filter to runs for this job name.")
    ] = None,
    ...
) -> str:
    """List recent Dagster+ runs. Filter by job name, run IDs, status,
    tags, or time range."""
    limit = min(limit, 100)
    filter_args = {}
    if job_name:
        filter_args["pipelineName"] = job_name
    ...
    data = gql(LIST_RUNS_QUERY, {"filter": filter_args or None, ...})
    return json.dumps(data["runsOrError"], indent=2)
```

Key patterns:

- **Tool description**: Function docstring
- **Parameter descriptions**: `Annotated[type, Field(description=...)]`
- **Enum constraints**: `Literal["QUEUED", "NOT_STARTED", ...]` for status
  filters
- **Dict params**: `dict[str, str]` for tags (generates correct
  `additionalProperties`)
- **Return type**: `str` — each handler returns `json.dumps(...)` of the
  relevant response data
- **Error handling**: `try/except` wrapping in each handler, returning error
  text
- **Custom logic preserved inline**:
  - `list_runs`: builds `filter_args` dict from optional params
  - `list_stale_assets`: Python-side filtering by group and staleness category
  - `get_run_logs`: client-side `filter_types` filtering after fetch

### `__main__.py`

```python
from .server import server

from . import tools  # noqa: F401 — triggers decorator registration

server.run(transport="stdio")
```

## Tools (all 15, behavior unchanged)

| Tool                              | Custom Logic                         |
| --------------------------------- | ------------------------------------ |
| `list_runs`                       | Filter dict building from params     |
| `get_run`                         | Straight query                       |
| `get_run_logs`                    | Client-side `filter_types` filtering |
| `get_run_compute_logs`            | Straight query                       |
| `get_captured_logs_metadata`      | Straight query                       |
| `get_daemon_health`               | Nested key extraction                |
| `list_code_locations`             | Straight query                       |
| `list_stale_assets`               | Python-side group/category filtering |
| `get_asset_materializations`      | Asset key split, partition wrapping  |
| `get_asset_partition_statuses`    | Asset key split                      |
| `get_asset_check_executions`      | Asset key split                      |
| `get_asset_condition_evaluations` | Asset key split                      |
| `get_tick_history`                | Default repository name              |
| `list_backfills`                  | Straight query                       |
| `get_backfill`                    | Straight query                       |

## Invocation Change

**Before:** `uv run mcp/dagster_plus.py` **After:**
`uv run python -m dagster_plus` (run from `mcp/` directory)

The package uses relative imports (`from .server import ...`), so it must be
invoked as a package. Running from the `mcp/` directory avoids shadowing the
`mcp` SDK package (the project's `mcp/` directory has no `__init__.py` and is
not itself a Python package).

Update references in:

- `mcp/CLAUDE.md` (running instructions)
- `.claude/settings.json` or `.claude/settings.local.json` (MCP server config,
  if present)

## What Gets Eliminated

- `list_tools()` function and 15 manual `types.Tool(inputSchema={...})` dicts
  (~420 lines)
- `call_tool()` if/elif dispatch chain (~250 lines)
- `import mcp.types as types`

## What Gets Added

- 4 new files with ~20 lines of boilerplate total
- `Annotated` and `Field` imports
- `Literal` types for enum constraints

## Risks & Mitigations

1. **Schema equivalence**: FastMCP may generate slightly different schema
   structure (e.g., `$defs` for Literals). MCP clients validate loosely — no
   functional impact. Spot-check a few tools after migration.

2. **Package naming**: The project's `mcp/` directory has no `__init__.py` and
   does not shadow the `mcp` SDK. The `dagster_plus/` package uses relative
   imports and is invoked from `mcp/` as working directory
   (`uv run python -m dagster_plus`). Verified that `import mcp` resolves to the
   SDK, not the project directory.

3. **Invocation path**: MCP server configs must be updated from
   `uv run mcp/dagster_plus.py` to `uv run python -m mcp.dagster_plus`.

4. **Parameter descriptions**: FastMCP does not extract descriptions from
   docstrings — only from `Field(description=...)`. All 15 tools must use
   `Annotated[type, Field(description=...)]` to preserve parameter docs.
