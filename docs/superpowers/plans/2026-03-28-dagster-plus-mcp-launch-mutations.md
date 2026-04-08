# Dagster+ MCP Launch Mutation Tools — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `launch_run`, `launch_multiple_runs`, and `reexecute_run` mutation
tools to the `dagster_plus` MCP server with a confirm-flag preview pattern.

**Architecture:** Asset-centric tool signatures with `confirm: bool = False`
parameter. Preview mode (`confirm=False`) builds and returns the GraphQL params
as JSON. Execute mode (`confirm=True`) sends the mutation via the existing
`gql()` helper. A shared `_build_execution_params` helper converts asset-centric
arguments into `ExecutionParams` dicts.

**Tech Stack:** Python 3.13, FastMCP (`mcp` SDK), `httpx` (via existing
`gql()`), Dagster+ GraphQL API.

**Spec:**
`docs/superpowers/specs/2026-03-28-dagster-plus-mcp-launch-mutations-design.md`

---

## File Structure

| File                          | Role                                                            |
| ----------------------------- | --------------------------------------------------------------- |
| `mcp/dagster_plus/queries.py` | Modify — add 3 mutation strings                                 |
| `mcp/dagster_plus/tools.py`   | Modify — add `_build_execution_params` helper, 3 tool functions |
| `mcp/dagster_plus/CLAUDE.md`  | Modify — document mutation tools and confirm pattern            |

No new files created. No changes to `server.py` or `__main__.py`.

---

### Task 1: Add GraphQL mutation strings to `queries.py`

**Files:**

- Modify: `mcp/dagster_plus/queries.py` (append after line 491)

- [ ] **Step 1: Add `LAUNCH_RUN_MUTATION`**

Append to the end of `mcp/dagster_plus/queries.py`:

```python
LAUNCH_RUN_MUTATION = """
mutation LaunchRun($executionParams: ExecutionParams!) {
  launchRun(executionParams: $executionParams) {
    __typename
    ... on LaunchRunSuccess {
      run {
        id
        jobName
        status
        creationTime
        assetSelection { path }
        tags { key value }
        repositoryOrigin {
          repositoryName
          repositoryLocationName
        }
      }
    }
    ... on PythonError { message stack }
    ... on InvalidSubsetError { message }
    ... on PipelineNotFoundError { message }
    ... on RunConfigValidationInvalid {
      errors { message reason }
    }
    ... on RunConflict { message }
    ... on UnauthorizedError { message }
    ... on ConflictingExecutionParamsError { message }
    ... on PresetNotFoundError { message }
    ... on NoModeProvidedError { message }
    ... on InvalidStepError { invalidStepKey }
    ... on InvalidOutputError { stepKey invalidOutputName }
  }
}
"""
```

- [ ] **Step 2: Add `LAUNCH_MULTIPLE_RUNS_MUTATION`**

Append immediately after:

```python
LAUNCH_MULTIPLE_RUNS_MUTATION = """
mutation LaunchMultipleRuns($executionParamsList: [ExecutionParams!]!) {
  launchMultipleRuns(executionParamsList: $executionParamsList) {
    __typename
    ... on LaunchMultipleRunsResult {
      launchMultipleRunsResult {
        __typename
        ... on LaunchRunSuccess {
          run { id jobName status creationTime assetSelection { path } }
        }
        ... on PythonError { message }
        ... on RunConflict { message }
        ... on UnauthorizedError { message }
      }
    }
    ... on PythonError { message stack }
  }
}
"""
```

- [ ] **Step 3: Add `LAUNCH_RUN_REEXECUTION_MUTATION`**

Append immediately after:

```python
LAUNCH_RUN_REEXECUTION_MUTATION = """
mutation LaunchRunReexecution($reexecutionParams: ReexecutionParams!) {
  launchRunReexecution(reexecutionParams: $reexecutionParams) {
    __typename
    ... on LaunchRunSuccess {
      run {
        id
        jobName
        status
        creationTime
        parentRunId
        rootRunId
        assetSelection { path }
        tags { key value }
      }
    }
    ... on PythonError { message stack }
    ... on PipelineNotFoundError { message }
    ... on RunConflict { message }
    ... on UnauthorizedError { message }
  }
}
"""
```

- [ ] **Step 4: Verify import works**

Run:

```bash
cd /workspaces/teamster/mcp && DAGSTER_CLOUD_API_TOKEN=test uv run python -c "from dagster_plus.queries import LAUNCH_RUN_MUTATION, LAUNCH_MULTIPLE_RUNS_MUTATION, LAUNCH_RUN_REEXECUTION_MUTATION; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add mcp/dagster_plus/queries.py
git commit -m "feat(mcp): add launch run GraphQL mutation strings"
```

---

### Task 2: Add `_build_execution_params` helper and `launch_run` tool

**Files:**

- Modify: `mcp/dagster_plus/tools.py`

- [ ] **Step 1: Add imports for new mutation queries**

In `mcp/dagster_plus/tools.py`, update the import block from `.queries` (lines
8–24) to also import the new mutations. Add these three to the import list:

```python
    LAUNCH_MULTIPLE_RUNS_MUTATION,
    LAUNCH_RUN_MUTATION,
    LAUNCH_RUN_REEXECUTION_MUTATION,
```

The full import block will be (alphabetical order maintained):

```python
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
    LAUNCH_MULTIPLE_RUNS_MUTATION,
    LAUNCH_RUN_MUTATION,
    LAUNCH_RUN_REEXECUTION_MUTATION,
    LIST_RUNS_QUERY,
    RUN_BY_ID_QUERY,
    RUN_LOGS_QUERY,
    STALE_ASSETS_QUERY,
    TICK_HISTORY_QUERY,
)
```

- [ ] **Step 2: Add `ReexecutionStrategy` type alias**

After the existing `BackfillStatus` literal (line 41), add:

```python
ReexecutionStrategy = Literal["FROM_FAILURE", "FROM_ASSET_FAILURE", "ALL_STEPS"]
```

- [ ] **Step 3: Add `_build_execution_params` helper**

After the type aliases (after `StalenessCategory`), add:

```python
def _build_execution_params(
    asset_keys: list[str],
    repository_location_name: str,
    repository_name: str = "__repository__",
    tags: dict[str, str] | None = None,
    run_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an ExecutionParams dict from asset-centric arguments."""
    params: dict[str, Any] = {
        "selector": {
            "repositoryLocationName": repository_location_name,
            "repositoryName": repository_name,
            "assetSelection": [
                {"path": key.split("/")} for key in asset_keys
            ],
        },
    }
    if run_config:
        params["runConfigData"] = run_config
    if tags:
        params["executionMetadata"] = {
            "tags": [{"key": k, "value": v} for k, v in tags.items()],
        }
    return params
```

- [ ] **Step 4: Add `launch_run` tool**

Append after all existing tool functions (after the `get_backfill` function,
currently ending at line 471):

```python
@server.tool()
def launch_run(
    asset_keys: Annotated[
        list[str],
        Field(
            description=(
                "Asset keys to materialize, as slash-separated strings "
                "(e.g. ['school/source/table'])."
            ),
        ),
    ],
    repository_location_name: Annotated[
        str,
        Field(description="The code location name (e.g. 'kipptaf')."),
    ],
    repository_name: Annotated[
        str,
        Field(description="The repository name (default '__repository__')."),
    ] = "__repository__",
    tags: Annotated[
        dict[str, str] | None,
        Field(description="Optional key/value tags for the run."),
    ] = None,
    run_config: Annotated[
        dict[str, Any] | None,
        Field(description="Optional run config overrides."),
    ] = None,
    confirm: Annotated[
        bool,
        Field(
            description=(
                "False (default) returns a preview of what would be launched. "
                "True executes the mutation."
            ),
        ),
    ] = False,
) -> str:
    """Launch a Dagster+ run to materialize selected assets. Call with confirm=False first to preview, then confirm=True to execute."""
    params = _build_execution_params(
        asset_keys=asset_keys,
        repository_location_name=repository_location_name,
        repository_name=repository_name,
        tags=tags,
        run_config=run_config,
    )
    if not confirm:
        return json.dumps(
            {
                "mode": "preview",
                "execution_params": params,
                "action_required": "Call again with confirm=True to execute.",
            },
            indent=2,
        )
    data = gql(LAUNCH_RUN_MUTATION, {"executionParams": params})
    return json.dumps(data["launchRun"], indent=2)
```

- [ ] **Step 5: Verify import works**

Run:

```bash
cd /workspaces/teamster/mcp && DAGSTER_CLOUD_API_TOKEN=test uv run python -c "from dagster_plus.tools import launch_run; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add mcp/dagster_plus/tools.py
git commit -m "feat(mcp): add _build_execution_params helper and launch_run tool"
```

---

### Task 3: Add `launch_multiple_runs` tool

**Files:**

- Modify: `mcp/dagster_plus/tools.py`

- [ ] **Step 1: Add `launch_multiple_runs` tool**

Append after the `launch_run` function:

```python
@server.tool()
def launch_multiple_runs(
    runs: Annotated[
        list[dict[str, Any]],
        Field(
            description=(
                "List of run specs. Each dict must have 'asset_keys' (list of "
                "slash-separated strings) and 'repository_location_name' (str). "
                "Optional: 'repository_name' (str, default '__repository__'), "
                "'tags' (dict[str, str]), 'run_config' (dict)."
            ),
        ),
    ],
    confirm: Annotated[
        bool,
        Field(
            description=(
                "False (default) returns a preview of what would be launched. "
                "True executes the mutation."
            ),
        ),
    ] = False,
) -> str:
    """Launch multiple Dagster+ runs in a single batch. Call with confirm=False first to preview, then confirm=True to execute."""
    params_list = [
        _build_execution_params(
            asset_keys=r["asset_keys"],
            repository_location_name=r["repository_location_name"],
            repository_name=r.get("repository_name", "__repository__"),
            tags=r.get("tags"),
            run_config=r.get("run_config"),
        )
        for r in runs
    ]
    if not confirm:
        return json.dumps(
            {
                "mode": "preview",
                "runs": params_list,
                "action_required": "Call again with confirm=True to execute.",
            },
            indent=2,
        )
    data = gql(
        LAUNCH_MULTIPLE_RUNS_MUTATION,
        {"executionParamsList": params_list},
    )
    return json.dumps(data["launchMultipleRuns"], indent=2)
```

- [ ] **Step 2: Verify import works**

Run:

```bash
cd /workspaces/teamster/mcp && DAGSTER_CLOUD_API_TOKEN=test uv run python -c "from dagster_plus.tools import launch_multiple_runs; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add mcp/dagster_plus/tools.py
git commit -m "feat(mcp): add launch_multiple_runs tool"
```

---

### Task 4: Add `reexecute_run` tool

**Files:**

- Modify: `mcp/dagster_plus/tools.py`

- [ ] **Step 1: Add `reexecute_run` tool**

Append after the `launch_multiple_runs` function:

```python
@server.tool()
def reexecute_run(
    parent_run_id: Annotated[
        str,
        Field(description="The run ID (UUID) of the failed run to re-execute."),
    ],
    strategy: Annotated[
        ReexecutionStrategy,
        Field(
            description=(
                "Re-execution strategy: FROM_FAILURE (retry from failed step), "
                "FROM_ASSET_FAILURE (retry from failed asset), or "
                "ALL_STEPS (re-run everything)."
            ),
        ),
    ],
    extra_tags: Annotated[
        dict[str, str] | None,
        Field(description="Optional additional tags for the new run."),
    ] = None,
    confirm: Annotated[
        bool,
        Field(
            description=(
                "False (default) returns a preview with parent run details. "
                "True executes the mutation."
            ),
        ),
    ] = False,
) -> str:
    """Re-execute a previous Dagster+ run with the given strategy. Call with confirm=False first to preview parent run details, then confirm=True to execute."""
    if not confirm:
        parent_data = gql(RUN_BY_ID_QUERY, {"runId": parent_run_id})
        return json.dumps(
            {
                "mode": "preview",
                "parent_run": parent_data["runOrError"],
                "strategy": strategy,
                "extra_tags": extra_tags,
                "action_required": "Call again with confirm=True to execute.",
            },
            indent=2,
        )
    reexecution_params: dict[str, Any] = {
        "parentRunId": parent_run_id,
        "strategy": strategy,
    }
    if extra_tags:
        reexecution_params["extraTags"] = [
            {"key": k, "value": v} for k, v in extra_tags.items()
        ]
    data = gql(
        LAUNCH_RUN_REEXECUTION_MUTATION,
        {"reexecutionParams": reexecution_params},
    )
    return json.dumps(data["launchRunReexecution"], indent=2)
```

- [ ] **Step 2: Verify import works**

Run:

```bash
cd /workspaces/teamster/mcp && DAGSTER_CLOUD_API_TOKEN=test uv run python -c "from dagster_plus.tools import reexecute_run; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add mcp/dagster_plus/tools.py
git commit -m "feat(mcp): add reexecute_run tool"
```

---

### Task 5: Update `CLAUDE.md` documentation

**Files:**

- Modify: `mcp/dagster_plus/CLAUDE.md`

- [ ] **Step 1: Add mutation tools section**

After the "Diagnosing degraded assets" section (end of file), append:

```markdown
## Mutation tools

Three tools launch runs via GraphQL mutations. All use a **confirm flag
pattern**: `confirm=False` (default) returns a preview of what would be sent;
`confirm=True` executes the mutation. No server-side state — preview and execute
are independent calls.

| Tool                   | Description                                                                   |
| ---------------------- | ----------------------------------------------------------------------------- |
| `launch_run`           | Materialize selected assets in a code location                                |
| `launch_multiple_runs` | Batch-launch multiple asset materializations                                  |
| `reexecute_run`        | Re-execute a previous run (`FROM_FAILURE`, `FROM_ASSET_FAILURE`, `ALL_STEPS`) |

### Usage pattern

1. Call with `confirm=False` (or omit) to preview the execution params
2. Review the preview JSON
3. Call again with `confirm=True` to execute

### Schema gotchas (mutations)

- `ExecutionParams.selector` uses `assetSelection` (list of `AssetKeyInput`),
  not `assetKeys` — tools handle this conversion from slash-separated strings
- `ReexecutionParams.extraTags` uses `[ExecutionTag!]` format (`key`/`value`
  objects), not a flat dict — tools handle this conversion
- `launchMultipleRuns` returns a nested result: the outer union has
  `LaunchMultipleRunsResult`, whose `launchMultipleRunsResult` field is a list
  of per-run `LaunchRunResult` unions
```

- [ ] **Step 2: Commit**

```bash
git add mcp/dagster_plus/CLAUDE.md
git commit -m "docs(mcp): document launch mutation tools and confirm pattern"
```

---

### Task 6: Final verification

- [ ] **Step 1: Verify full module import**

Run:

```bash
cd /workspaces/teamster/mcp && DAGSTER_CLOUD_API_TOKEN=test uv run python -c "
from dagster_plus import tools
names = [n for n in dir(tools) if not n.startswith('_')]
print('\n'.join(names))
"
```

Expected output should include all existing tools plus `launch_multiple_runs`,
`launch_run`, `reexecute_run`.

- [ ] **Step 2: Verify tool registration on the FastMCP server**

Run:

```bash
cd /workspaces/teamster/mcp && DAGSTER_CLOUD_API_TOKEN=test uv run python -c "
from dagster_plus.tools import server
import asyncio
tools = asyncio.run(server.list_tools())
for t in tools:
    print(t.name)
"
```

Expected: all 18 tools listed (15 existing + 3 new).

- [ ] **Step 3: Verify linting passes**

Run:

```bash
cd /workspaces/teamster && /workspaces/teamster/.trunk/tools/trunk check mcp/dagster_plus/queries.py mcp/dagster_plus/tools.py
```

Expected: no errors (warnings acceptable).
