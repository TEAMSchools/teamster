# CLAUDE.md — `mcp/`

## Overview

MCP (Model Context Protocol) servers that expose Dagster+ operational data to AI
assistants. Each server is a standalone Python script run via `uv run`.

## MCP Tool Selection

For ad-hoc queries against known production tables (no `ref()` needed), use the
BigQuery MCP directly. Use dbt MCP's `show` only when `ref()` / `source()`
resolution is needed — it adds compilation overhead and the target determines
the environment.

## `dagster_plus.py`

An MCP server that exposes Dagster+ run logs, compute logs, daemon health, asset
staleness, automation condition evaluations, tick history, backfills, and more
via the Dagster+ GraphQL API.

### Running

```bash
uv run mcp/dagster_plus.py
```

### Environment Variables

| Variable                        | Required | Default   | Description                  |
| ------------------------------- | -------- | --------- | ---------------------------- |
| `DAGSTER_CLOUD_API_TOKEN`       | Yes      | —         | Dagster+ user or agent token |
| `DAGSTER_CLOUD_ORGANIZATION_ID` | No       | `kipptaf` | Org slug                     |
| `DAGSTER_CLOUD_DEPLOYMENT`      | No       | `prod`    | Deployment name              |

### Tools

| Tool                              | Description                                                                |
| --------------------------------- | -------------------------------------------------------------------------- |
| `list_runs`                       | List runs; filter by job, run IDs, status, tags, or time range             |
| `get_run`                         | Full details for one run: asset selection, re-execution lineage, step keys |
| `get_run_logs`                    | Structured event log (paginated); filter by event type                     |
| `get_run_compute_logs`            | Raw stdout/stderr for a step; logKey from `LogsCapturedEvent`              |
| `get_captured_logs_metadata`      | Signed download URLs for full stdout/stderr log files                      |
| `get_daemon_health`               | Health, heartbeat time, and errors for all daemons                         |
| `list_code_locations`             | All workspace code locations and their load status                         |
| `list_stale_assets`               | Assets with stale status; filter by `CODE`/`DATA`/`DEPENDENCIES` or group  |
| `get_asset_materializations`      | Recent materialization history for an asset with metadata                  |
| `get_asset_partition_statuses`    | Partition counts (materialized/failed/missing) for a partitioned asset     |
| `get_asset_check_executions`      | Pass/fail history for a named asset check                                  |
| `get_asset_condition_evaluations` | Automation condition evaluation tree per daemon tick                       |
| `get_tick_history`                | Schedule/sensor tick history; diagnose why an instigator isn't firing      |
| `list_backfills`                  | List backfills; filter by status                                           |
| `get_backfill`                    | Full details for a single backfill                                         |

### GraphQL Schema Reference

All queries are verified against the Dagster source:
[`dagster-graphql/dagster_graphql/schema`](https://github.com/dagster-io/dagster/tree/master/python_modules/dagster-graphql/dagster_graphql/schema)

**Do not write or modify GraphQL queries from memory.** Field names diverge from
what you'd expect (see gotchas below). Always verify against the source before
adding or changing a query.

#### Schema gotchas

These are non-obvious divergences from what you'd expect. Always verify new or
changed queries against the schema source above.

- **`pipelineName` not `jobName`**: `RunsFilter` uses `pipelineName` to filter
  by job name (legacy naming).
- **`hasTerminatePermission` not `hasCancelPermission` on `Run`**: `Run` has no
  `hasCancelPermission` field despite what the UI suggests. Note:
  `PartitionBackfill` does have `hasCancelPermission` — the field is
  type-specific.
- **`MessageEvent` is an interface**: The actual union is `DagsterRunEvent` with
  43 concrete members — you must use inline fragments.
- **No `ioType` on compute logs**: `capturedLogs` returns both `stdout` and
  `stderr` together; there is no enum to select one.
- **`numRequested` only**: `AssetConditionEvaluationRecord` has no `numSkipped`
  or `numDiscarded` — use the evaluation node tree instead.
- **`evaluationNodes` not `evaluation.evaluationNodes`**: The flat list is the
  current API; the nested union is legacy.
- **Group filtering requires `AssetGroupSelector`**: All three fields are
  required, so `list_stale_assets` filters by group in Python instead.
- **Timestamps are Unix floats**: `createdAfter`/`createdBefore` etc. on
  `RunsFilter` are `Float`, not ISO strings.

### Pagination

`list_runs`, `get_run_logs`, `get_asset_condition_evaluations`,
`get_asset_check_executions`, and `list_backfills` return a `cursor` field. Pass
it back as `cursor` on the next call to page forward. Timestamp-based filtering
is not supported by the API — paginate and filter client-side.

## BigQuery MCP

The BigQuery MCP tool truncates results at 50 rows. When querying
`INFORMATION_SCHEMA.COLUMNS` for tables with >50 columns, paginate with
`WHERE ordinal_position > N` to get all rows.
