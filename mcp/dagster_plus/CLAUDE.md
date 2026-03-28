# CLAUDE.md — `mcp/dagster_plus/`

FastMCP server exposing Dagster+ operational data via GraphQL.

## Package Structure

- `server.py` — `FastMCP` instance, env vars, `gql()` client
- `queries.py` — GraphQL query strings (verify against schema before modifying)
- `tools.py` — sync `@server.tool()` handlers with
  `Annotated[type, Field(description=...)]`
- `__main__.py` — entry point (imports `tools` to trigger registration)

**Adding a tool:** Add query to `queries.py`, add `@server.tool()` function to
`tools.py`. FastMCP auto-generates JSON schema from type hints.

**Import constraint:** `mcp/` has no `__init__.py` (would shadow the `mcp` SDK).
Use relative imports. Pyright `reportMissingImports` warnings are expected.

**Testing imports:** `DAGSTER_CLOUD_API_TOKEN` is required at import time — use
`DAGSTER_CLOUD_API_TOKEN=test` prefix when verifying outside the MCP runtime.

## Running

```bash
cd mcp && uv run python -m dagster_plus
```

## Environment Variables

| Variable                        | Required | Default   | Description      |
| ------------------------------- | -------- | --------- | ---------------- |
| `DAGSTER_CLOUD_API_TOKEN`       | Yes      | —         | User/agent token |
| `DAGSTER_CLOUD_ORGANIZATION_ID` | No       | `kipptaf` | Org slug         |
| `DAGSTER_CLOUD_DEPLOYMENT`      | No       | `prod`    | Deployment name  |

## GraphQL Schema Reference

Queries verified against
[`dagster-graphql/dagster_graphql/schema`](https://github.com/dagster-io/dagster/tree/master/python_modules/dagster-graphql/dagster_graphql/schema).
**Do not write or modify queries from memory.** Always verify against source.

### Schema gotchas

- `RunsFilter` uses `pipelineName`, not `jobName` (legacy naming)
- `Run` has `hasTerminatePermission`, not `hasCancelPermission`
  (`PartitionBackfill` does have `hasCancelPermission`)
- `MessageEvent` is an interface — use inline fragments for `DagsterRunEvent`
- `capturedLogs` returns both stdout/stderr — no `ioType` selector
- `AssetConditionEvaluationRecord` has `numRequested` only — no
  `numSkipped`/`numDiscarded`
- `evaluationNodes` is top-level, not nested under `evaluation`
- `AssetGroupSelector` requires all three fields — `list_stale_assets` filters
  by group in Python instead
- Timestamps (`createdAfter`, etc.) are Unix floats, not ISO strings

## Pagination

`list_runs`, `get_run_logs`, `get_asset_condition_evaluations`,
`get_asset_check_executions`, and `list_backfills` return a `cursor`. Pass it
back to page forward. No server-side timestamp filtering — paginate and filter
client-side.

## Diagnosing degraded assets

1. `list_runs(statuses=["FAILURE"])` for recent failures — more targeted than
   `list_stale_assets` (can exceed token limits at 1.8M+ chars)
2. `get_run` for step keys/asset selection, then cross-reference BigQuery
   schemas (`get_table_info`) against dbt contract YAML
3. `get_run_compute_logs` returns null for GKE runs (ephemeral pods) — use
   BigQuery MCP and dbt compilation instead
4. `get_run_logs` returns `timestamp: null` for non-`MessageEvent` types —
   timestamp only on `MessageEvent` subtypes

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
