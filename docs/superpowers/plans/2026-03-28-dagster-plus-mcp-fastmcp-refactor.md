# Dagster+ MCP Server FastMCP Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `mcp/dagster_plus.py` from a 1250-line single file using the
low-level MCP Server API into a `mcp/dagster_plus/` package using FastMCP,
eliminating ~670 lines of boilerplate.

**Architecture:** Split into 4 modules — `server.py` (FastMCP instance + `gql()`
helper), `queries.py` (GraphQL strings), `tools.py` (15 decorated tool
handlers), `__main__.py` (entry point). FastMCP auto-generates JSON schemas from
type hints and handles tool dispatch.

**Tech Stack:** Python 3.13, MCP SDK 1.26.0 (FastMCP), Pydantic v2, httpx

---

## File Structure

| Action | Path                           | Responsibility                                  |
| ------ | ------------------------------ | ----------------------------------------------- |
| Create | `mcp/dagster_plus/__init__.py` | Empty package marker                            |
| Create | `mcp/dagster_plus/__main__.py` | Entry point: import tools, run server           |
| Create | `mcp/dagster_plus/server.py`   | FastMCP instance, env vars, `gql()` helper      |
| Create | `mcp/dagster_plus/queries.py`  | 15 GraphQL query string constants               |
| Create | `mcp/dagster_plus/tools.py`    | 15 `@server.tool()` decorated handler functions |
| Modify | `.mcp.json:7`                  | Update invocation command                       |
| Modify | `mcp/CLAUDE.md:7-9`            | Update running instructions                     |
| Delete | `mcp/dagster_plus.py`          | Replaced by package                             |

---

### Task 1: Create `mcp/dagster_plus/` package skeleton

**Files:**

- Create: `mcp/dagster_plus/__init__.py`
- Create: `mcp/dagster_plus/server.py`
- Create: `mcp/dagster_plus/__main__.py`

- [ ] **Step 1: Create package directory**

```bash
mkdir -p mcp/dagster_plus
```

- [ ] **Step 2: Create empty `__init__.py`**

Create `mcp/dagster_plus/__init__.py` with empty content.

- [ ] **Step 3: Create `server.py`**

Create `mcp/dagster_plus/server.py`:

```python
"""FastMCP server instance and GraphQL client for Dagster+."""

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

DAGSTER_CLOUD_API_TOKEN = os.environ.get("DAGSTER_CLOUD_API_TOKEN", "")
DAGSTER_CLOUD_ORGANIZATION_ID = os.environ.get(
    "DAGSTER_CLOUD_ORGANIZATION_ID", "kipptaf"
)
DAGSTER_CLOUD_DEPLOYMENT = os.environ.get("DAGSTER_CLOUD_DEPLOYMENT", "prod")

GRAPHQL_URL = (
    f"https://{DAGSTER_CLOUD_ORGANIZATION_ID}.dagster.cloud"
    f"/{DAGSTER_CLOUD_DEPLOYMENT}/graphql"
)

server = FastMCP("dagster-plus")


def gql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query against the Dagster+ API."""
    with httpx.Client(timeout=60) as client:
        response = client.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables or {}},
            headers={
                "Dagster-Cloud-Api-Token": DAGSTER_CLOUD_API_TOKEN,
                "Content-Type": "application/json",
            },
        )
        if not response.is_success:
            raise RuntimeError(
                f"Dagster API {response.status_code}: {response.text[:500]}"
            )
        data = response.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data["data"]
```

- [ ] **Step 4: Create `__main__.py`**

Create `mcp/dagster_plus/__main__.py`:

```python
"""Entry point for the Dagster+ MCP server."""

from .server import server

from . import tools  # noqa: F401 — triggers decorator registration

server.run(transport="stdio")
```

- [ ] **Step 5: Verify the package imports cleanly**

```bash
cd /workspaces/teamster && uv run python -c "from mcp.server.fastmcp import FastMCP; print('FastMCP OK')"
```

Expected: `FastMCP OK`

- [ ] **Step 6: Commit**

```bash
git add mcp/dagster_plus/__init__.py mcp/dagster_plus/server.py mcp/dagster_plus/__main__.py
git commit -m "refactor(mcp): add dagster_plus package skeleton with FastMCP server"
```

---

### Task 2: Move GraphQL queries to `queries.py`

**Files:**

- Create: `mcp/dagster_plus/queries.py`

- [ ] **Step 1: Create `queries.py`**

Create `mcp/dagster_plus/queries.py` containing all 15 query constants copied
verbatim from `mcp/dagster_plus.py` lines 62–550. The file should start with:

```python
"""GraphQL query strings for the Dagster+ API."""
```

Then all constants in order:

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

Copy each query string exactly as-is from the original file. No modifications.

- [ ] **Step 2: Verify imports**

```bash
cd /workspaces/teamster && uv run python -c "from mcp.dagster_plus.queries import LIST_RUNS_QUERY; print(LIST_RUNS_QUERY[:40])"
```

Expected: First 40 characters of the LIST_RUNS_QUERY string.

Wait — this import won't work because `mcp/` is not a Python package (no
`__init__.py`). Instead test with:

```bash
cd /workspaces/teamster/mcp && uv run python -c "from dagster_plus.queries import LIST_RUNS_QUERY; print(LIST_RUNS_QUERY[:40])"
```

Expected: starts with a newline then `query ListRuns`

- [ ] **Step 3: Commit**

```bash
git add mcp/dagster_plus/queries.py
git commit -m "refactor(mcp): move GraphQL queries to queries.py"
```

---

### Task 3: Implement tool handlers — runs and logs (5 tools)

**Files:**

- Create: `mcp/dagster_plus/tools.py`

This task creates `tools.py` with the first 5 tools: `list_runs`, `get_run`,
`get_run_logs`, `get_run_compute_logs`, `get_captured_logs_metadata`.

- [ ] **Step 1: Create `tools.py` with the first 5 tools**

Create `mcp/dagster_plus/tools.py`:

```python
"""Dagster+ MCP tool handlers."""

import json
from typing import Annotated, Any, Literal

from pydantic import Field

from .queries import (
    ASSET_CHECK_EXECUTIONS_QUERY,
    ASSET_CONDITION_EVALUATIONS_QUERY,
    ASSET_MATERIALIZATIONS_QUERY,
    ASSET_PARTITION_STATUSES_QUERY,
    BACKFILL_QUERY,
    BACKFILLS_QUERY,
    CAPTURED_LOGS_METADATA_QUERY,
    CODE_LOCATIONS_QUERY,
    COMPUTE_LOGS_QUERY,
    DAEMON_HEALTH_QUERY,
    LIST_RUNS_QUERY,
    RUN_BY_ID_QUERY,
    RUN_LOGS_QUERY,
    STALE_ASSETS_QUERY,
    TICK_HISTORY_QUERY,
)
from .server import gql, server


RunStatus = Literal[
    "QUEUED",
    "NOT_STARTED",
    "MANAGED",
    "STARTING",
    "STARTED",
    "SUCCESS",
    "FAILURE",
    "CANCELING",
    "CANCELED",
]

TickStatus = Literal["SUCCESS", "FAILURE", "SKIPPED", "STARTED"]

BackfillStatus = Literal["REQUESTED", "CANCELING", "CANCELED", "FAILED", "COMPLETED"]

StalenessCategory = Literal["CODE", "DATA", "DEPENDENCIES"]


@server.tool()
async def list_runs(
    limit: Annotated[
        int,
        Field(description="Max number of runs to return (default 20, max 100)."),
    ] = 20,
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous list_runs call."),
    ] = None,
    job_name: Annotated[
        str | None,
        Field(description="Filter to runs for this job name."),
    ] = None,
    run_ids: Annotated[
        list[str] | None,
        Field(description="Filter to specific run IDs."),
    ] = None,
    statuses: Annotated[
        list[RunStatus] | None,
        Field(description="Filter to runs with these statuses."),
    ] = None,
    tags: Annotated[
        dict[str, str] | None,
        Field(description="Filter to runs with these key/value tags."),
    ] = None,
    created_after: Annotated[
        float | None,
        Field(description="Filter to runs created after this Unix timestamp."),
    ] = None,
    created_before: Annotated[
        float | None,
        Field(description="Filter to runs created before this Unix timestamp."),
    ] = None,
    updated_after: Annotated[
        float | None,
        Field(description="Filter to runs updated after this Unix timestamp."),
    ] = None,
    updated_before: Annotated[
        float | None,
        Field(description="Filter to runs updated before this Unix timestamp."),
    ] = None,
) -> str:
    """List recent Dagster+ runs. Filter by job name, run IDs, status, tags, or time range. Returns run IDs, job names, statuses, asset selections, re-execution lineage, and timestamps."""
    limit = min(limit, 100)
    filter_args: dict[str, Any] = {}
    if job_name:
        filter_args["pipelineName"] = job_name
    if run_ids:
        filter_args["runIds"] = run_ids
    if statuses:
        filter_args["statuses"] = statuses
    if tags:
        filter_args["tags"] = [{"key": k, "value": v} for k, v in tags.items()]
    if created_after:
        filter_args["createdAfter"] = created_after
    if created_before:
        filter_args["createdBefore"] = created_before
    if updated_after:
        filter_args["updatedAfter"] = updated_after
    if updated_before:
        filter_args["updatedBefore"] = updated_before
    data = gql(
        LIST_RUNS_QUERY,
        {
            "filter": filter_args or None,
            "cursor": cursor,
            "limit": limit,
        },
    )
    return json.dumps(data["runsOrError"], indent=2)


@server.tool()
async def get_run(
    run_id: Annotated[
        str,
        Field(description="The run ID (UUID) to look up."),
    ],
) -> str:
    """Get full details for a single Dagster+ run by ID. Includes asset selection, re-execution lineage (parentRunId, rootRunId), step keys, step counts, and tags."""
    data = gql(RUN_BY_ID_QUERY, {"runId": run_id})
    return json.dumps(data["runOrError"], indent=2)


@server.tool()
async def get_run_logs(
    run_id: Annotated[
        str,
        Field(description="The run ID to fetch logs for."),
    ],
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous get_run_logs call."),
    ] = None,
    limit: Annotated[
        int,
        Field(
            description=(
                "Max events to fetch per page (default 100, max 1000). "
                "When filter_types is set, filtering happens client-side "
                "after fetching — increase limit to see more matching events."
            ),
        ),
    ] = 100,
    filter_types: Annotated[
        list[str] | None,
        Field(
            description=(
                "Only return events of these __typename values, e.g. "
                "['ExecutionStepFailureEvent', 'RunFailureEvent']. "
                "Omit to return all event types."
            ),
        ),
    ] = None,
) -> str:
    """Get the structured event log for a Dagster+ run. Includes step start/success/failure events, log messages, asset materializations, engine errors, and resource init failures. Paginate with cursor if hasMore is true."""
    limit = min(limit, 1000)
    data = gql(
        RUN_LOGS_QUERY,
        {
            "runId": run_id,
            "afterCursor": cursor,
            "limit": limit,
        },
    )
    result = data["logsForRun"]
    if filter_types:
        filter_set = set(filter_types)
        if isinstance(result, dict) and "events" in result:
            result = {
                **result,
                "events": [
                    e
                    for e in result["events"]
                    if e.get("__typename") in filter_set
                ],
            }
    return json.dumps(result, indent=2)


@server.tool()
async def get_run_compute_logs(
    log_key: Annotated[
        list[str],
        Field(
            description=(
                'The logKey array from a LogsCapturedEvent, e.g. '
                '["<run_id>", "compute_logs", "<step_key>"].'
            ),
        ),
    ],
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous call."),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Max bytes to return (default 50000)."),
    ] = 50000,
) -> str:
    """Get raw stdout and stderr compute logs for a step in a Dagster+ run. First use get_run_logs to find LogsCapturedEvent entries, which contain the logKey needed here. Returns both stdout and stderr as separate fields."""
    data = gql(
        COMPUTE_LOGS_QUERY,
        {
            "logKey": log_key,
            "cursor": cursor,
            "limit": limit,
        },
    )
    return json.dumps(data["capturedLogs"], indent=2)


@server.tool()
async def get_captured_logs_metadata(
    log_key: Annotated[
        list[str],
        Field(description="The logKey array from a LogsCapturedEvent."),
    ],
) -> str:
    """Get signed download URLs and storage locations for stdout/stderr compute logs. Use when logs are too large to stream via get_run_compute_logs. logKey comes from a LogsCapturedEvent."""
    data = gql(
        CAPTURED_LOGS_METADATA_QUERY,
        {"logKey": log_key},
    )
    return json.dumps(data["capturedLogsMetadata"], indent=2)
```

- [ ] **Step 2: Verify the module imports**

```bash
cd /workspaces/teamster/mcp && uv run python -c "from dagster_plus.tools import list_runs, get_run; print('5 tools OK')"
```

Expected: `5 tools OK`

- [ ] **Step 3: Commit**

```bash
git add mcp/dagster_plus/tools.py
git commit -m "refactor(mcp): add first 5 tool handlers (runs and logs)"
```

---

### Task 4: Add infrastructure tools (3 tools)

**Files:**

- Modify: `mcp/dagster_plus/tools.py`

Append `get_daemon_health`, `list_code_locations`, and `list_stale_assets` to
`tools.py`.

- [ ] **Step 1: Append 3 tool functions to `tools.py`**

Add after the `get_captured_logs_metadata` function:

```python


@server.tool()
async def get_daemon_health() -> str:
    """Get the health status of all Dagster+ daemons (scheduler, sensor, run coordinator, etc.). Returns whether each daemon is healthy, its last heartbeat time, and any error messages."""
    data = gql(DAEMON_HEALTH_QUERY)
    return json.dumps(
        data["instance"]["daemonHealth"]["allDaemonStatuses"], indent=2
    )


@server.tool()
async def list_code_locations() -> str:
    """List all code locations in the Dagster+ workspace and their load status. Shows which locations loaded successfully and which have errors (e.g. import failures after a deploy)."""
    data = gql(CODE_LOCATIONS_QUERY)
    return json.dumps(data["workspaceOrError"], indent=2)


@server.tool()
async def list_stale_assets(
    category: Annotated[
        StalenessCategory | None,
        Field(description="Filter to a specific staleness category. Omit for all."),
    ] = None,
    group: Annotated[
        str | None,
        Field(description="Filter to assets in this group name."),
    ] = None,
) -> str:
    """List assets with a stale status in Dagster+. CODE = code version changed since last materialization (shown as 'unsynced' in the UI); DATA = upstream data updated; DEPENDENCIES = upstream dependency structure changed. Returns asset key, group, compute kind, owners, jobs, and stale causes."""
    data = gql(STALE_ASSETS_QUERY)
    nodes = data["assetNodes"]
    stale = [n for n in nodes if n.get("staleStatus") == "STALE"]
    if group:
        stale = [n for n in stale if n.get("groupName") == group]
    if category:
        stale = [
            n
            for n in stale
            if any(
                c.get("category") == category for c in n.get("staleCauses", [])
            )
        ]
    return json.dumps(stale, indent=2)
```

- [ ] **Step 2: Verify imports**

```bash
cd /workspaces/teamster/mcp && uv run python -c "from dagster_plus.tools import get_daemon_health, list_code_locations, list_stale_assets; print('8 tools OK')"
```

Expected: `8 tools OK`

- [ ] **Step 3: Commit**

```bash
git add mcp/dagster_plus/tools.py
git commit -m "refactor(mcp): add infrastructure tool handlers (daemon, code locations, stale assets)"
```

---

### Task 5: Add asset tools (4 tools)

**Files:**

- Modify: `mcp/dagster_plus/tools.py`

Append `get_asset_materializations`, `get_asset_partition_statuses`,
`get_asset_check_executions`, and `get_asset_condition_evaluations` to
`tools.py`.

- [ ] **Step 1: Append 4 tool functions to `tools.py`**

Add after `list_stale_assets`:

```python


@server.tool()
async def get_asset_materializations(
    asset_key: Annotated[
        str,
        Field(description="Asset key as slash-separated string, e.g. 'school/source/table'."),
    ],
    limit: Annotated[
        int,
        Field(description="Number of materializations to return (default 10, max 100)."),
    ] = 10,
    partition: Annotated[
        str | None,
        Field(description="Filter to a specific partition key."),
    ] = None,
) -> str:
    """Get recent materialization history for an asset. Returns timestamps, run IDs, partition keys, and metadata entries for each materialization."""
    asset_key_path = asset_key.split("/")
    limit = min(limit, 100)
    data = gql(
        ASSET_MATERIALIZATIONS_QUERY,
        {
            "assetKey": {"path": asset_key_path},
            "limit": limit,
            "partitions": [partition] if partition else None,
        },
    )
    nodes = data["assetNodes"]
    result = (
        nodes[0]
        if nodes
        else {"assetKey": {"path": asset_key_path}, "assetMaterializations": []}
    )
    return json.dumps(result, indent=2)


@server.tool()
async def get_asset_partition_statuses(
    asset_key: Annotated[
        str,
        Field(description="Asset key as slash-separated string."),
    ],
) -> str:
    """Get partition materialization status for a partitioned asset. Returns aggregate counts (materialized, failed, missing) and, for time-partitioned assets, a range breakdown."""
    asset_key_path = asset_key.split("/")
    data = gql(
        ASSET_PARTITION_STATUSES_QUERY,
        {"assetKey": {"path": asset_key_path}},
    )
    nodes = data["assetNodes"]
    result = nodes[0] if nodes else {}
    return json.dumps(result, indent=2)


@server.tool()
async def get_asset_check_executions(
    asset_key: Annotated[
        str,
        Field(description="Asset key as slash-separated string."),
    ],
    check_name: Annotated[
        str,
        Field(description="Name of the asset check."),
    ],
    limit: Annotated[
        int,
        Field(description="Number of executions to return (default 10, max 50)."),
    ] = 10,
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous call."),
    ] = None,
) -> str:
    """Get execution history for a specific asset check. Returns pass/fail status, severity, description, and metadata for each execution."""
    asset_key_path = asset_key.split("/")
    limit = min(limit, 50)
    data = gql(
        ASSET_CHECK_EXECUTIONS_QUERY,
        {
            "assetKey": {"path": asset_key_path},
            "checkName": check_name,
            "limit": limit,
            "cursor": cursor,
        },
    )
    return json.dumps(data["assetCheckExecutions"], indent=2)


@server.tool()
async def get_asset_condition_evaluations(
    asset_key: Annotated[
        str,
        Field(description="Asset key as slash-separated string."),
    ],
    limit: Annotated[
        int,
        Field(description="Number of evaluation records to return (default 10, max 50)."),
    ] = 10,
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous call."),
    ] = None,
) -> str:
    """Get automation condition evaluation history for an asset. Shows why the daemon requested or skipped each materialization — includes the full condition node tree with each node's label, operator type, and true/candidate counts."""
    asset_key_path = asset_key.split("/")
    limit = min(limit, 50)
    data = gql(
        ASSET_CONDITION_EVALUATIONS_QUERY,
        {
            "assetKey": {"path": asset_key_path},
            "limit": limit,
            "cursor": cursor,
        },
    )
    return json.dumps(data["assetConditionEvaluationRecordsOrError"], indent=2)
```

- [ ] **Step 2: Verify imports**

```bash
cd /workspaces/teamster/mcp && uv run python -c "from dagster_plus.tools import get_asset_materializations, get_asset_condition_evaluations; print('12 tools OK')"
```

Expected: `12 tools OK`

- [ ] **Step 3: Commit**

```bash
git add mcp/dagster_plus/tools.py
git commit -m "refactor(mcp): add asset tool handlers (materializations, partitions, checks, conditions)"
```

---

### Task 6: Add remaining tools (3 tools)

**Files:**

- Modify: `mcp/dagster_plus/tools.py`

Append `get_tick_history`, `list_backfills`, and `get_backfill` to `tools.py`.

- [ ] **Step 1: Append 3 tool functions to `tools.py`**

Add after `get_asset_condition_evaluations`:

```python


@server.tool()
async def get_tick_history(
    name: Annotated[
        str,
        Field(description="The schedule or sensor name."),
    ],
    repository_location_name: Annotated[
        str,
        Field(description="The code location name (e.g. 'kipptaf')."),
    ],
    repository_name: Annotated[
        str,
        Field(description="The repository name within the code location (default '__repository__')."),
    ] = "__repository__",
    limit: Annotated[
        int,
        Field(description="Number of ticks to return (default 20)."),
    ] = 20,
    statuses: Annotated[
        list[TickStatus] | None,
        Field(description="Filter to ticks with these statuses. Omit for all."),
    ] = None,
) -> str:
    """Get tick history for a schedule or sensor. Shows each evaluation tick with its status (SUCCESS, FAILURE, SKIPPED), run IDs launched, skip reason, and error details. Essential for diagnosing why a schedule or sensor is not firing."""
    data = gql(
        TICK_HISTORY_QUERY,
        {
            "name": name,
            "repositoryLocationName": repository_location_name,
            "repositoryName": repository_name,
            "limit": limit,
            "statuses": statuses or None,
        },
    )
    return json.dumps(data["instigationStateOrError"], indent=2)


@server.tool()
async def list_backfills(
    status: Annotated[
        BackfillStatus | None,
        Field(description="Filter to backfills with this status."),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Number of backfills to return (default 20, max 100)."),
    ] = 20,
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous call."),
    ] = None,
) -> str:
    """List backfills in the Dagster+ deployment. Returns backfill ID, status, asset selection, partition counts by run status, and any errors."""
    limit = min(limit, 100)
    data = gql(
        BACKFILLS_QUERY,
        {
            "status": status,
            "cursor": cursor,
            "limit": limit,
        },
    )
    return json.dumps(data["partitionBackfillsOrError"], indent=2)


@server.tool()
async def get_backfill(
    backfill_id: Annotated[
        str,
        Field(description="The backfill ID to look up."),
    ],
) -> str:
    """Get details for a single backfill by ID. Returns asset selection, partition names, status counts, error, and metadata."""
    data = gql(BACKFILL_QUERY, {"backfillId": backfill_id})
    return json.dumps(data["partitionBackfillOrError"], indent=2)
```

- [ ] **Step 2: Verify all 15 tools register**

```bash
cd /workspaces/teamster/mcp && uv run python -c "
from dagster_plus.server import server
from dagster_plus import tools  # noqa: F401
tool_names = [t.name for t in server._tool_manager.list_tools()]
print(f'{len(tool_names)} tools registered')
for name in sorted(tool_names):
    print(f'  {name}')
"
```

Expected output:

```text
15 tools registered
  get_asset_check_executions
  get_asset_condition_evaluations
  get_asset_materializations
  get_asset_partition_statuses
  get_backfill
  get_captured_logs_metadata
  get_daemon_health
  get_run
  get_run_compute_logs
  get_run_logs
  get_tick_history
  list_backfills
  list_code_locations
  list_runs
  list_stale_assets
```

- [ ] **Step 3: Commit**

```bash
git add mcp/dagster_plus/tools.py
git commit -m "refactor(mcp): add remaining tool handlers (tick history, backfills)"
```

---

### Task 7: Delete old file and update config

**Files:**

- Delete: `mcp/dagster_plus.py`
- Modify: `.mcp.json:7`
- Modify: `mcp/CLAUDE.md`

- [ ] **Step 1: Delete the old single-file server**

```bash
cd /workspaces/teamster && git rm mcp/dagster_plus.py
```

- [ ] **Step 2: Update `.mcp.json` invocation**

In `.mcp.json`, change line 7 from:

```text
"DAGSTER_CLOUD_API_TOKEN=$(op read 'op://Data Team/Dagster Cloud Agent/credential') uv run --group mcp python mcp/dagster_plus.py"
```

to:

```text
"DAGSTER_CLOUD_API_TOKEN=$(op read 'op://Data Team/Dagster Cloud Agent/credential') uv run --group mcp python -m dagster_plus"
```

Also add `"cwd"` to the dagster server config so it runs from `mcp/`:

```json
{
  "mcpServers": {
    "dagster": {
      "command": "bash",
      "args": [
        "-c",
        "DAGSTER_CLOUD_API_TOKEN=$(op read 'op://Data Team/Dagster Cloud Agent/credential') uv run --group mcp python -m dagster_plus"
      ],
      "cwd": "mcp",
      "env": {
        "DAGSTER_CLOUD_ORGANIZATION_ID": "kipptaf",
        "DAGSTER_CLOUD_DEPLOYMENT": "prod"
      }
    }
  }
}
```

(Keep the other servers unchanged.)

- [ ] **Step 3: Update `mcp/CLAUDE.md` running instructions**

Change the Running section from:

```bash
uv run mcp/dagster_plus.py
```

to:

```bash
cd mcp && uv run python -m dagster_plus
```

- [ ] **Step 4: Verify the package runs as expected**

```bash
cd /workspaces/teamster/mcp && timeout 3 uv run python -m dagster_plus 2>&1 || true
```

Expected: The server starts and waits for stdio input, then times out after 3
seconds. No import errors or crashes.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "refactor(mcp): delete old single-file server, update config and docs"
```

---

### Task 8: Lint and final verification

**Files:**

- Possibly modify: `mcp/dagster_plus/tools.py` (lint fixes)

- [ ] **Step 1: Run trunk check on the new package**

```bash
cd /workspaces/teamster && trunk check mcp/dagster_plus/
```

Fix any lint issues reported.

- [ ] **Step 2: Verify all 15 tools are registered with correct names**

```bash
cd /workspaces/teamster/mcp && uv run python -c "
from dagster_plus.server import server
from dagster_plus import tools  # noqa: F401

expected = {
    'list_runs', 'get_run', 'get_run_logs', 'get_run_compute_logs',
    'get_captured_logs_metadata', 'get_daemon_health', 'list_code_locations',
    'list_stale_assets', 'get_asset_materializations',
    'get_asset_partition_statuses', 'get_asset_check_executions',
    'get_asset_condition_evaluations', 'get_tick_history',
    'list_backfills', 'get_backfill',
}
actual = {t.name for t in server._tool_manager.list_tools()}
assert actual == expected, f'Mismatch: missing={expected - actual}, extra={actual - expected}'
print('All 15 tools registered correctly')
"
```

Expected: `All 15 tools registered correctly`

- [ ] **Step 3: Commit any lint fixes**

```bash
git add mcp/dagster_plus/
git commit -m "style(mcp): fix lint issues in dagster_plus package"
```

(Skip this commit if no lint fixes were needed.)
