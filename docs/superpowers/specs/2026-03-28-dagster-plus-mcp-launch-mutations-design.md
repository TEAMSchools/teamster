# Dagster+ MCP Launch Mutation Tools

## Summary

Add three mutation tools to the `dagster_plus` MCP server for launching runs,
launching multiple runs in batch, and re-executing failed runs. All tools use an
asset-centric API with a `confirm` flag pattern: `confirm=False` (default)
returns a preview; `confirm=True` executes the mutation.

## Decisions

- **Asset-first signatures** — asset keys as slash-separated strings, matching
  existing query tool conventions. No job-name-based launching.
- **Confirm flag pattern** — single tool per operation with
  `confirm: bool = False`. Preview mode builds the params and returns a summary.
  Execute mode sends the GraphQL mutation. No server-side state.
- **Simple reexecution only** — `reexecute_run` uses `ReexecutionParams` (parent
  run ID + strategy), not full `ExecutionParams`.
- **No guardrails beyond confirmation** — caller is trusted.

## Tool Signatures

### `launch_run`

```python
@server.tool()
def launch_run(
    asset_keys: list[str],              # slash-separated, e.g. ["school/source/table"]
    repository_location_name: str,      # e.g. "kipptaf"
    repository_name: str = "__repository__",
    tags: dict[str, str] | None = None,
    run_config: dict[str, Any] | None = None,
    confirm: bool = False,
) -> str:
```

- **Preview** (`confirm=False`): Builds `ExecutionParams`, returns JSON summary
  with asset keys, code location, tags, and
  `"action_required": "Call again with confirm=True to execute"`.
- **Execute** (`confirm=True`): Sends `launchRun` mutation. Returns run ID,
  status, job name from `LaunchRunSuccess`.

### `launch_multiple_runs`

```python
@server.tool()
def launch_multiple_runs(
    runs: list[dict[str, Any]],         # each: asset_keys, repository_location_name,
                                        # optional: repository_name, tags, run_config
    confirm: bool = False,
) -> str:
```

- **Preview**: Validates and summarizes each run entry.
- **Execute**: Sends `launchMultipleRuns` mutation. Returns per-run results.

### `reexecute_run`

```python
ReexecutionStrategy = Literal["FROM_FAILURE", "FROM_ASSET_FAILURE", "ALL_STEPS"]

@server.tool()
def reexecute_run(
    parent_run_id: str,
    strategy: ReexecutionStrategy,
    extra_tags: dict[str, str] | None = None,
    confirm: bool = False,
) -> str:
```

- **Preview**: Fetches parent run via `RUN_BY_ID_QUERY`, returns summary with
  parent run status, job name, asset selection, chosen strategy.
- **Execute**: Sends `launchRunReexecution` with `reexecutionParams`. Returns
  new run ID and status.

## GraphQL Mutations

### `LAUNCH_RUN_MUTATION`

```graphql
mutation LaunchRun($executionParams: ExecutionParams!) {
  launchRun(executionParams: $executionParams) {
    __typename
    ... on LaunchRunSuccess {
      run {
        id
        jobName
        status
        creationTime
        assetSelection {
          path
        }
        tags {
          key
          value
        }
        repositoryOrigin {
          repositoryName
          repositoryLocationName
        }
      }
    }
    ... on PythonError {
      message
      stack
    }
    ... on InvalidSubsetError {
      message
    }
    ... on PipelineNotFoundError {
      message
    }
    ... on RunConfigValidationInvalid {
      errors {
        message
        reason
      }
    }
    ... on RunConflict {
      message
    }
    ... on UnauthorizedError {
      message
    }
    ... on ConflictingExecutionParamsError {
      message
    }
    ... on PresetNotFoundError {
      message
    }
    ... on NoModeProvidedError {
      message
    }
    ... on InvalidStepError {
      invalidStepKey
    }
    ... on InvalidOutputError {
      stepKey
      invalidOutputName
    }
  }
}
```

### `LAUNCH_MULTIPLE_RUNS_MUTATION`

```graphql
mutation LaunchMultipleRuns($executionParamsList: [ExecutionParams!]!) {
  launchMultipleRuns(executionParamsList: $executionParamsList) {
    __typename
    ... on LaunchMultipleRunsResult {
      launchMultipleRunsResult {
        __typename
        ... on LaunchRunSuccess {
          run {
            id
            jobName
            status
            creationTime
            assetSelection {
              path
            }
          }
        }
        ... on PythonError {
          message
        }
        ... on RunConflict {
          message
        }
        ... on UnauthorizedError {
          message
        }
      }
    }
    ... on PythonError {
      message
      stack
    }
  }
}
```

### `LAUNCH_RUN_REEXECUTION_MUTATION`

```graphql
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
        assetSelection {
          path
        }
        tags {
          key
          value
        }
      }
    }
    ... on PythonError {
      message
      stack
    }
    ... on PipelineNotFoundError {
      message
    }
    ... on RunConflict {
      message
    }
    ... on UnauthorizedError {
      message
    }
  }
}
```

## Preview Logic

No server-side state. Preview mode builds the exact params dict that would be
sent to the GraphQL API and returns it as JSON with `"mode": "preview"` and
`"action_required": "Call again with confirm=True to execute"`.

For `reexecute_run`, preview also fetches the parent run details (status, job
name, asset selection) to give the caller context about what will be
re-executed.

## File Changes

| File                          | Change                                                                                        |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| `mcp/dagster_plus/queries.py` | Add `LAUNCH_RUN_MUTATION`, `LAUNCH_MULTIPLE_RUNS_MUTATION`, `LAUNCH_RUN_REEXECUTION_MUTATION` |
| `mcp/dagster_plus/tools.py`   | Add `launch_run`, `launch_multiple_runs`, `reexecute_run` with confirm flag logic             |
| `mcp/dagster_plus/CLAUDE.md`  | Document new mutation tools and confirmation pattern                                          |

No new files. No changes to `server.py` or `__main__.py`.

## Helper: `_build_execution_params`

Shared helper to build the `ExecutionParams` dict from asset-centric arguments:

```python
def _build_execution_params(
    asset_keys: list[str],
    repository_location_name: str,
    repository_name: str = "__repository__",
    tags: dict[str, str] | None = None,
    run_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

Converts slash-separated asset keys to `{"path": [...]}` format, builds the
`JobOrPipelineSelector` with `assetSelection`, and wraps tags into
`ExecutionMetadata`.
