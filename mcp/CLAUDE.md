# CLAUDE.md — `mcp/`

## Overview

MCP (Model Context Protocol) servers that expose Dagster+ operational data to
AI assistants. Each server is a standalone Python script run via `uv run`.

## `dagster_plus.py`

An MCP server that exposes Dagster+ run logs, compute logs, daemon health,
asset staleness, and automation condition evaluations via the Dagster+ GraphQL
API.

### Running

```bash
uv run mcp/dagster_plus.py
```

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DAGSTER_CLOUD_API_TOKEN` | Yes | — | Dagster+ user or agent token |
| `DAGSTER_CLOUD_ORGANIZATION_ID` | No | `teamschools` | Org slug |
| `DAGSTER_CLOUD_DEPLOYMENT` | No | `prod` | Deployment name |

### Tools

| Tool | Description |
|---|---|
| `list_runs` | List recent runs; filter by job name, status, or tags |
| `get_run` | Get details for a single run by ID |
| `get_run_logs` | Structured event log for a run (paginated); filter by event type |
| `get_run_compute_logs` | Raw stdout/stderr for a step; logKey comes from `LogsCapturedEvent` |
| `get_daemon_health` | Health status and heartbeat errors for all daemons |
| `list_stale_assets` | Assets with stale status; filter by `CODE`/`DATA`/`DEPENDENCIES` category or group name |
| `get_asset_condition_evaluations` | Automation condition evaluation history for an asset, including the full condition node tree |

### GraphQL Schema Reference

All queries are verified against the Dagster source:
[`dagster-graphql/dagster_graphql/schema`](https://github.com/dagster-io/dagster/tree/master/python_modules/dagster-graphql/dagster_graphql/schema)

**Do not write or modify GraphQL queries from memory.** Field names are
non-obvious and diverge from what you might expect (e.g. `capturedLogs`
returns `stdout`/`stderr` strings, not a `data` field; there is no
`ComputeIOType` enum). Always verify against the source before adding or
changing a query.

Key schema notes:

- `logsForRun` returns `EventConnectionOrError` — union includes
  `EventConnection`, `RunNotFoundError`, and `PythonError`. Handle all three.
- `capturedLogs(logKey, cursor, limit)` — no `ioType` parameter; returns
  `stdout: String`, `stderr: String`, `cursor: String`.
- `assetNodes` group filtering requires a full `AssetGroupSelector`
  (`groupName`, `repositoryName`, `repositoryLocationName`) — do group
  filtering in Python instead.
- `AssetConditionEvaluationRecord` has `numRequested` but no `numSkipped` or
  `numDiscarded`. Use `evaluationNodes` (the flat list of
  `AutomationConditionEvaluationNode`) rather than the legacy
  `evaluation.evaluationNodes` union which has three concrete types.
- `StaleCauseCategory` enum: `CODE`, `DATA`, `DEPENDENCIES`.

### Pagination

`list_runs`, `get_run_logs`, and `get_asset_condition_evaluations` all return
a `cursor` field. Pass it back as the `cursor` argument on the next call to
page forward. Timestamp-based filtering is not supported by the API — paginate
and filter client-side.
