# CLAUDE.md — `mcp/`

## Overview

MCP (Model Context Protocol) servers that expose Dagster+ operational data to
AI assistants. Each server is a standalone Python script run via `uv run`.

## `dagster_plus.py`

An MCP server that exposes Dagster+ run logs, compute logs, daemon health,
asset staleness, automation condition evaluations, tick history, backfills,
and more via the Dagster+ GraphQL API.

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
| `list_runs` | List runs; filter by job, run IDs, status, tags, or time range |
| `get_run` | Full details for one run: asset selection, re-execution lineage, step keys |
| `get_run_logs` | Structured event log (paginated); filter by event type |
| `get_run_compute_logs` | Raw stdout/stderr for a step; logKey from `LogsCapturedEvent` |
| `get_captured_logs_metadata` | Signed download URLs for full stdout/stderr log files |
| `get_daemon_health` | Health, heartbeat time, and errors for all daemons |
| `list_code_locations` | All workspace code locations and their load status |
| `list_stale_assets` | Assets with stale status; filter by `CODE`/`DATA`/`DEPENDENCIES` or group |
| `get_asset_materializations` | Recent materialization history for an asset with metadata |
| `get_asset_partition_statuses` | Partition counts (materialized/failed/missing) for a partitioned asset |
| `get_asset_check_executions` | Pass/fail history for a named asset check |
| `get_asset_condition_evaluations` | Automation condition evaluation tree per daemon tick |
| `get_tick_history` | Schedule/sensor tick history; diagnose why an instigator isn't firing |
| `list_backfills` | List backfills; filter by status |
| `get_backfill` | Full details for a single backfill |

### GraphQL Schema Reference

All queries are verified against the Dagster source:
[`dagster-graphql/dagster_graphql/schema`](https://github.com/dagster-io/dagster/tree/master/python_modules/dagster-graphql/dagster_graphql/schema)

**Do not write or modify GraphQL queries from memory.** Field names diverge
from what you'd expect (see gotchas below). Always verify against the source
before adding or changing a query.

#### Key schema notes

**Runs:**
- `RunsFilter` accepts: `pipelineName`, `runIds`, `statuses`, `tags`,
  `createdAfter`, `createdBefore`, `updatedAfter`, `updatedBefore`
  (all Unix timestamps as Float). No `mode` in modern Dagster.
- `Run` has `parentRunId`/`rootRunId` for re-execution chains, `updateTime`
  for last status change, `stepKeysToExecute` for partial runs.
- `hasCancelPermission` does not exist — the correct field is
  `hasTerminatePermission`.

**Logs:**
- `logsForRun` returns `EventConnectionOrError` — union includes
  `EventConnection`, `RunNotFoundError`, and `PythonError`. Handle all three.
- `MessageEvent` is an **interface**, not a concrete type. The union is
  `DagsterRunEvent` with 43 concrete members.

**Compute logs:**
- `capturedLogs(logKey, cursor, limit)` — no `ioType` parameter; returns
  `stdout: String`, `stderr: String`, `cursor: String`.
- `capturedLogsMetadata(logKey)` returns `stdoutDownloadUrl`,
  `stdoutLocation`, `stderrDownloadUrl`, `stderrLocation` (signed URLs).

**Asset staleness:**
- `AssetNode.staleStatus` and `staleCauses` both accept an optional
  `partition: String` argument.
- `StaleCauseCategory` enum: `CODE`, `DATA`, `DEPENDENCIES`.
- `StaleCause` fields: `key`, `partitionKey`, `category`, `reason`,
  `dependency`, `dependencyPartitionKey`.
- `assetNodes` group filtering requires a full `AssetGroupSelector`
  (all three fields required) — filter by group in Python instead.

**Asset condition evaluations:**
- `AssetConditionEvaluationRecord` has `numRequested` only — no
  `numSkipped` or `numDiscarded`.
- Use `evaluationNodes` (flat list of `AutomationConditionEvaluationNode`)
  rather than the legacy `evaluation.evaluationNodes` union.
- `AutomationConditionEvaluationNode` fields include `userLabel`,
  `expandedLabel`, `operatorType`, `isPartitioned`, `sinceMetadata`.
- `sinceMetadata` (only populated for `SinceCondition` nodes) has
  `triggerEvaluationId`, `triggerTimestamp`, `resetEvaluationId`,
  `resetTimestamp`.

**Tick history:**
- `instigationStateOrError` takes `InstigationSelector` with `name`,
  `repositoryName`, `repositoryLocationName`. For single-repo code
  locations `repositoryName` is `"__repository__"`.
- `InstigationTick.statuses` filter enum values:
  `SUCCESS`, `FAILURE`, `SKIPPED`, `STARTED`.

**Partitions:**
- `assetPartitionStatuses` returns a union of `TimePartitionStatuses`
  (with `ranges[{status, startKey, endKey, startTime, endTime}]`) and
  `DefaultPartitionStatuses` (with `materializedPartitions`,
  `failedPartitions`, etc. as string arrays).
- `partitionStats` gives aggregate counts: `numMaterialized`,
  `numMaterializing`, `numPartitions`, `numFailed`.

**Backfills:**
- `partitionBackfillsOrError(status, cursor, limit)` — `status` is a
  single `BulkActionStatus` enum value
  (`REQUESTED`, `CANCELING`, `CANCELED`, `FAILED`, `COMPLETED`).

### Pagination

`list_runs`, `get_run_logs`, `get_asset_condition_evaluations`,
`get_asset_check_executions`, and `list_backfills` return a `cursor` field.
Pass it back as `cursor` on the next call to page forward.
Timestamp-based filtering is not supported by the API — paginate and filter
client-side.
