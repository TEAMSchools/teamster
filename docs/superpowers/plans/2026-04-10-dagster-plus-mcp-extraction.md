# Extract `dagster-plus-mcp` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `mcp/dagster_plus/` from the teamster monorepo into a
standalone `TEAMSchools/dagster-plus-mcp` GitHub repo, rename the Python package
to `dagster_plus_mcp`, and consume it back in teamster as a git dependency.

**Architecture:** The existing FastMCP server code moves verbatim into a new
repo with a renamed package directory. The only code change is making two env
vars required instead of defaulted. Teamster adds the new repo as a git dep in
its `dev` dependency group and updates `.mcp.json` to point at a new run script.

**Tech Stack:** Python 3.13+, FastMCP (`mcp` SDK), `httpx`, `hatchling`, `uv`,
GitHub CLI (`gh`)

**Spec:**
`docs/superpowers/specs/2026-04-10-dagster-plus-mcp-extraction-design.md`

---

## Task 1: Create the GitHub repo

**Files:** None (GitHub API only)

- [ ] **Step 1: Create the empty repo**

```bash
gh repo create TEAMSchools/dagster-plus-mcp --public --clone
```

Expected: repo created at `https://github.com/TEAMSchools/dagster-plus-mcp`,
cloned to `./dagster-plus-mcp/`.

- [ ] **Step 2: Confirm the clone**

```bash
cd dagster-plus-mcp && git remote -v
```

Expected: `origin` pointing at
`https://github.com/TEAMSchools/dagster-plus-mcp`.

---

## Task 2: Populate the new repo — package skeleton

**Files:**

- Create: `dagster-plus-mcp/pyproject.toml`
- Create: `dagster-plus-mcp/dagster_plus_mcp/__init__.py`
- Create: `dagster-plus-mcp/dagster_plus_mcp/__main__.py`

- [ ] **Step 1: Create `pyproject.toml`**

Write to `dagster-plus-mcp/pyproject.toml`:

```toml
[project]
name = "dagster-plus-mcp"
version = "0.1.0"
description = "MCP server for the Dagster+ GraphQL API"
requires-python = ">=3.13"
dependencies = ["mcp>=1.0.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["dagster_plus_mcp"]
```

- [ ] **Step 2: Create `__init__.py`**

Write to `dagster-plus-mcp/dagster_plus_mcp/__init__.py` — empty file (same as
current `mcp/dagster_plus/__init__.py`).

- [ ] **Step 3: Create `__main__.py`**

Write to `dagster-plus-mcp/dagster_plus_mcp/__main__.py`:

```python
"""Entry point for the Dagster+ MCP server."""

from . import tools  # trunk-ignore(ruff/F401): triggers @server.tool() registration
from .server import server

server.run(transport="stdio")
```

Identical to `mcp/dagster_plus/__main__.py` — relative imports are unchanged.

- [ ] **Step 4: Commit skeleton**

```bash
cd dagster-plus-mcp
git add pyproject.toml dagster_plus_mcp/__init__.py dagster_plus_mcp/__main__.py
git commit -m "feat: add package skeleton with pyproject.toml and entry point"
```

---

## Task 3: Populate the new repo — server, queries, tools

**Files:**

- Create: `dagster-plus-mcp/dagster_plus_mcp/server.py`
- Create: `dagster-plus-mcp/dagster_plus_mcp/queries.py`
- Create: `dagster-plus-mcp/dagster_plus_mcp/tools.py`

- [ ] **Step 1: Create `server.py`**

Copy `mcp/dagster_plus/server.py` to
`dagster-plus-mcp/dagster_plus_mcp/server.py` with one change — replace the two
`os.environ.get(...)` calls with `os.environ[...]`:

```python
"""FastMCP server instance and GraphQL client for Dagster+."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from mcp.server.fastmcp import FastMCP

logging.getLogger("httpx").setLevel(logging.WARNING)

DAGSTER_CLOUD_API_TOKEN = os.environ["DAGSTER_CLOUD_API_TOKEN"]
DAGSTER_CLOUD_ORGANIZATION_ID = os.environ["DAGSTER_CLOUD_ORGANIZATION_ID"]
DAGSTER_CLOUD_DEPLOYMENT = os.environ["DAGSTER_CLOUD_DEPLOYMENT"]

GRAPHQL_URL = (
    f"https://{DAGSTER_CLOUD_ORGANIZATION_ID}.dagster.cloud"
    f"/{DAGSTER_CLOUD_DEPLOYMENT}/graphql"
)

_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    global _client  # noqa: PLW0603
    _client = httpx.AsyncClient(
        base_url=GRAPHQL_URL,
        headers={
            "Dagster-Cloud-Api-Token": DAGSTER_CLOUD_API_TOKEN,
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    try:
        yield
    finally:
        await _client.aclose()
        _client = None


server = FastMCP(
    "dagster-plus",
    instructions=(
        "Dagster+ operational server for KIPP TEAM & Family Schools. "
        "To diagnose asset issues: use search_assets to discover assets by "
        "prefix, then get_asset_health for health status (HEALTHY, DEGRADED, "
        "WARNING, UNKNOWN) and get_asset_staleness for staleness root causes. "
        "To diagnose missed materializations (asset expected to materialize but "
        "didn't): (1) get_asset_condition_evaluations with limit=1 for the "
        "latest evaluation, (2) walk evaluationNodes from rootUniqueId — find "
        "the node where numTrue=0 that should be >0, userLabel/expandedLabel "
        "identifies which rule blocked it, (3) if the condition tree looks "
        "correct, get_tick_history for the sensor to check for errors or skips. "
        "Mutation tools (launch_run, launch_multiple_runs, "
        "reexecute_run) require confirm=True to execute — always preview first "
        "with confirm=False."
    ),
    lifespan=_lifespan,
)


class GraphQLError(Exception):
    """Structured error from the Dagster+ GraphQL API."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message)
        self.message = message
        self.details = details


async def gql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query against the Dagster+ API."""
    if _client is None:
        raise RuntimeError("HTTP client not initialized (lifespan not started)")
    response = await _client.post(
        "", json={"query": query, "variables": variables or {}}
    )
    if not response.is_success:
        raise GraphQLError(
            f"Dagster API returned {response.status_code}",
            details=response.text[:500],
        )
    data = response.json()
    if "errors" in data:
        raise GraphQLError("GraphQL query failed", details=data["errors"])
    return data["data"]
```

- [ ] **Step 2: Copy `queries.py` verbatim**

Copy `mcp/dagster_plus/queries.py` to
`dagster-plus-mcp/dagster_plus_mcp/queries.py`. No changes needed.

- [ ] **Step 3: Copy `tools.py` verbatim**

Copy `mcp/dagster_plus/tools.py` to
`dagster-plus-mcp/dagster_plus_mcp/tools.py`. No changes needed — all imports
are relative (`from .queries import ...`, `from .server import ...`).

- [ ] **Step 4: Verify import works**

```bash
cd dagster-plus-mcp
DAGSTER_CLOUD_API_TOKEN=test DAGSTER_CLOUD_ORGANIZATION_ID=test DAGSTER_CLOUD_DEPLOYMENT=test \
  uv run python -c "from dagster_plus_mcp.tools import list_runs, get_run; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd dagster-plus-mcp
git add dagster_plus_mcp/server.py dagster_plus_mcp/queries.py dagster_plus_mcp/tools.py
git commit -m "feat: add server, queries, and tools from teamster mcp/dagster_plus"
```

---

## Task 4: Populate the new repo — schema.json and CLAUDE.md

**Files:**

- Create: `dagster-plus-mcp/dagster_plus_mcp/schema.json`
- Create: `dagster-plus-mcp/CLAUDE.md`

- [ ] **Step 1: Copy `schema.json`**

Copy `mcp/dagster_plus/schema.json` to
`dagster-plus-mcp/dagster_plus_mcp/schema.json`. No changes.

- [ ] **Step 2: Create `CLAUDE.md`**

Copy `mcp/dagster_plus/CLAUDE.md` to `dagster-plus-mcp/CLAUDE.md` with these
changes:

- Title: `# CLAUDE.md — dagster-plus-mcp` (was `mcp/dagster_plus/`)
- Remove "Import constraint" paragraph (no longer relevant — standalone repo)
- "Testing imports" paragraph: update to note all three env vars are required
  (was just `DAGSTER_CLOUD_API_TOKEN`)
- "Running" section: command becomes `uv run python -m dagster_plus_mcp` (was
  `uv run --project mcp python -m dagster_plus`)
- "Environment Variables" table: remove Default column, all three rows say
  Required=Yes (no defaults)
- "schema.json" reference: path becomes `dagster_plus_mcp/schema.json` (was
  `mcp/dagster_plus/schema.json`)
- Remove "Live API testing" section (teamster-specific hook reference)
- "Diagnosing assets" section: remove "cross-reference BigQuery schemas" line
  (teamster-specific cross-MCP pattern)
- "get_run_compute_logs" quirk: remove "use BigQuery MCP and dbt compilation
  instead" (teamster-specific)
- All other sections (GraphQL Schema Reference, Schema gotchas, Pagination,
  Discovery tools, Mutation tools) copied verbatim

- [ ] **Step 3: Commit**

```bash
cd dagster-plus-mcp
git add dagster_plus_mcp/schema.json CLAUDE.md
git commit -m "docs: add CLAUDE.md and GraphQL schema introspection dump"
```

---

## Task 5: Push the new repo

- [ ] **Step 1: Push all commits**

```bash
cd dagster-plus-mcp
git push -u origin main
```

Expected: all commits pushed to
`https://github.com/TEAMSchools/dagster-plus-mcp`.

---

## Task 6: Teamster — add git dependency and update `.mcp.json`

**Files:**

- Modify: `pyproject.toml` (teamster root)
- Modify: `.mcp.json`
- Create: `.devcontainer/scripts/run-dagster-mcp.sh` (manual — protected path)

- [ ] **Step 1: Add git dep to `dev` group**

In `/workspaces/teamster/pyproject.toml`, change the `[dependency-groups]`
section from:

```toml
[dependency-groups]
dev = ["cron-descriptor>=1.4", "dagster-webserver", "pytest>=8.3.4"]
```

to:

```toml
[dependency-groups]
dev = [
    "cron-descriptor>=1.4",
    "dagster-plus-mcp @ git+https://github.com/TEAMSchools/dagster-plus-mcp.git",
    "dagster-webserver",
    "pytest>=8.3.4",
]
```

- [ ] **Step 2: Lock and verify the dependency resolves**

```bash
cd /workspaces/teamster
uv lock
```

Expected: `uv.lock` updated with `dagster-plus-mcp` entry.

- [ ] **Step 3: Verify import**

```bash
cd /workspaces/teamster
DAGSTER_CLOUD_API_TOKEN=test DAGSTER_CLOUD_ORGANIZATION_ID=test DAGSTER_CLOUD_DEPLOYMENT=test \
  uv run --group dev python -c "from dagster_plus_mcp.tools import list_runs; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Create run script (MANUAL — protected path)**

Create `.devcontainer/scripts/run-dagster-mcp.sh` with this content:

```bash
#!/usr/bin/env bash
DAGSTER_CLOUD_API_TOKEN=$(op read 'op://Data Team/Dagster Cloud Agent/credential')
export DAGSTER_CLOUD_API_TOKEN
exec uv run --group dev python -m dagster_plus_mcp
```

Then make it executable:

```bash
chmod +x .devcontainer/scripts/run-dagster-mcp.sh
```

> **This step must be done manually** — `.devcontainer/scripts/` is a protected
> path that Claude Code cannot write to.

- [ ] **Step 5: Update `.mcp.json`**

Change the `dagster` server entry in `.mcp.json` from:

```json
{
  "command": "bash",
  "args": ["mcp/dagster_plus/run.sh"],
  "env": {
    "DAGSTER_CLOUD_ORGANIZATION_ID": "kipptaf",
    "DAGSTER_CLOUD_DEPLOYMENT": "prod"
  }
}
```

to:

```json
{
  "command": "bash",
  "args": [".devcontainer/scripts/run-dagster-mcp.sh"],
  "env": {
    "DAGSTER_CLOUD_ORGANIZATION_ID": "kipptaf",
    "DAGSTER_CLOUD_DEPLOYMENT": "prod"
  }
}
```

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster
git add -u
git commit -m "feat: consume dagster-plus-mcp as git dependency"
```

---

## Task 7: Teamster — delete `mcp/` directory

**Files:**

- Delete: `mcp/pyproject.toml`
- Delete: `mcp/uv.lock`
- Delete: `mcp/CLAUDE.md`
- Delete: `mcp/dagster_plus/__init__.py`
- Delete: `mcp/dagster_plus/__main__.py`
- Delete: `mcp/dagster_plus/server.py`
- Delete: `mcp/dagster_plus/queries.py`
- Delete: `mcp/dagster_plus/tools.py`
- Delete: `mcp/dagster_plus/schema.json`
- Delete: `mcp/dagster_plus/CLAUDE.md`
- Delete: `mcp/dagster_plus/run.sh`

- [ ] **Step 1: Remove the entire `mcp/` directory**

```bash
cd /workspaces/teamster
git rm -r mcp/
```

Expected: all files under `mcp/` staged for deletion.

- [ ] **Step 2: Commit**

```bash
cd /workspaces/teamster
git commit -m "refactor: remove mcp/ directory, replaced by dagster-plus-mcp repo"
```

---

## Task 8: Verify end-to-end

- [ ] **Step 1: Verify import still works after deletion**

```bash
cd /workspaces/teamster
DAGSTER_CLOUD_API_TOKEN=test DAGSTER_CLOUD_ORGANIZATION_ID=test DAGSTER_CLOUD_DEPLOYMENT=test \
  uv run --group dev python -c "from dagster_plus_mcp.tools import list_runs, get_run, search_assets; print('OK')"
```

Expected: `OK`

- [ ] **Step 2: Verify MCP server starts (requires real token)**

This step requires a real `DAGSTER_CLOUD_API_TOKEN`. Run manually in the
terminal:

```bash
bash .devcontainer/scripts/run-dagster-mcp.sh
```

Expected: server starts on stdio, no errors. Ctrl+C to stop.
