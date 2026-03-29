# CLAUDE.md — `mcp/dagster_plus/`

FastMCP server exposing Dagster+ operational data via GraphQL.

## Package Structure

- `server.py` — `FastMCP` instance (with `instructions`), env vars, persistent
  `httpx.AsyncClient`, async `gql()` client, `GraphQLError` exception
- `queries.py` — GraphQL query strings (see GraphQL section below before
  modifying)
- `tools.py` — async `@server.tool()` handlers with
  `Annotated[type, Field(description=...)]`, wrapped with `@_handle_gql_errors`
  for structured error returns
- `__main__.py` — entry point (imports `tools` to trigger registration)

**Adding a tool:** Add query to `queries.py`, add `@server.tool()` function to
`tools.py` with the `@_handle_gql_errors` decorator. FastMCP auto-generates JSON
schema from type hints. Use `BaseModel` subclasses for complex input types (see
`RunSpec`).

**Import constraint:** `mcp/` has no `__init__.py` — adding one would shadow the
`mcp` SDK. The `dagster_plus` package is built via hatch (`mcp/pyproject.toml`).
Use relative imports. Pyright `reportMissingImports` warnings are expected.

**Testing imports:** `DAGSTER_CLOUD_API_TOKEN` is required at import time — use
`DAGSTER_CLOUD_API_TOKEN=test` prefix when verifying outside the MCP runtime.

## Running

```bash
uv run --project mcp python -m dagster_plus
```

## Environment Variables

| Variable                        | Required | Default   | Description      |
| ------------------------------- | -------- | --------- | ---------------- |
| `DAGSTER_CLOUD_API_TOKEN`       | Yes      | —         | User/agent token |
| `DAGSTER_CLOUD_ORGANIZATION_ID` | No       | `kipptaf` | Org slug         |
| `DAGSTER_CLOUD_DEPLOYMENT`      | No       | `prod`    | Deployment name  |

## GraphQL Schema Reference

New queries are sourced from the Dagster UI TypeScript at
[`js_modules/ui-core/src`](https://github.com/dagster-io/dagster/tree/master/js_modules/ui-core/src)
— no Python package exports client-side queries. Verify field names/types
against the Python schema in
[`dagster-graphql/dagster_graphql/schema`](https://github.com/dagster-io/dagster/tree/master/python_modules/dagster-graphql/dagster_graphql/schema).
**Do not write or modify queries from memory.**

### Schema gotchas

- `RunsFilter` uses `pipelineName`, not `jobName` (legacy naming)
- `Run` has `hasTerminatePermission`, not `hasCancelPermission`
  (`PartitionBackfill` does have `hasCancelPermission`)
- `MessageEvent` is an interface — use inline fragments for `DagsterRunEvent`
- `capturedLogs` returns both stdout/stderr — no `ioType` selector
- `AssetConditionEvaluationRecord` has `numRequested` only — no
  `numSkipped`/`numDiscarded`
- `evaluationNodes` is top-level, not nested under `evaluation`
- `AssetGroupSelector` requires all three fields (`groupName`,
  `repositoryLocationName`, `repositoryName`)
- Timestamps (`createdAfter`, etc.) are Unix floats, not ISO strings

## Pagination

`list_runs`, `get_run_logs`, `get_asset_condition_evaluations`,
`get_asset_check_executions`, `list_backfills`, and `search_assets` return a
`cursor`. Pass it back to page forward. No server-side timestamp filtering —
paginate and filter client-side.

## Diagnosing degraded assets

1. `search_assets(prefix="...")` to discover asset keys
2. `get_asset_health(asset_keys=[...])` for health status,
   `get_asset_staleness(asset_keys=[...])` for staleness root causes
3. `list_runs(statuses=["FAILURE"])` for broad failure scanning across all
   assets
4. `get_run` for step keys/asset selection, then cross-reference BigQuery
   schemas (`get_table_info`) against dbt contract YAML

### API quirks

- `get_run_compute_logs` returns null for GKE runs (ephemeral pods) — use
  BigQuery MCP and dbt compilation instead
- `get_run_logs` returns `timestamp: null` for non-`MessageEvent` types

## Live API testing

Security hooks block `op read` in Bash — smoke test against live Dagster Cloud
API manually in the terminal, not via Claude Code.

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
