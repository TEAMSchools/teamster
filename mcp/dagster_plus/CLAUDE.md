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
