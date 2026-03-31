---
name: day2
description: >-
  Use when performing daily platform health checks, triaging overnight Dagster
  run failures, investigating GKE cluster events, or reviewing automation sensor
  tick errors. Invoke at start of workday or after overnight batch windows.
---

# Day-2 Operations Check

Triage overnight platform health across Dagster+, GKE Autopilot, and automation
sensors. Produces a correlated timeline and action items.

## Procedure

### 1. Time window

Default: 5 PM ET previous business day to now. Accept user override. Convert to
both UTC (for GKE log queries) and Unix epoch (for Dagster API).

### 2. Failed runs

```python
mcp__dagster__list_runs(statuses=["FAILURE"], created_after=<epoch>)
```

For each failed run:

```python
mcp__dagster__get_run_logs(run_id=<id>,
  filter_types=["ExecutionStepFailureEvent", "RunFailureEvent", "EngineEvent"],
  limit=500)
```

Classify failures:

| Category            | Signals                                               |
| ------------------- | ----------------------------------------------------- |
| Node OOM / eviction | "low on resource: memory", exit 137, "Evicted"        |
| Scheduling failure  | "FailedScheduling", "Insufficient cpu/memory", taints |
| Code error          | `ExecutionStepFailureEvent` with Python traceback     |
| Infra timeout       | "run worker failed" without scheduling/OOM signals    |

Note `dagster/will_retry` and `dagster/auto_retry_run_id` tags. Query the retry
run to check if it succeeded.

### 3. Failed automation ticks

For each code location from `mcp__dagster__list_code_locations`:

```python
mcp__dagster__get_tick_history(
  name="<location>__automation_condition_sensor",
  repository_location_name="<location>",
  statuses=["FAILURE"], limit=20)
```

Filter to time window. Common errors:

| Error                             | Meaning                         |
| --------------------------------- | ------------------------------- |
| `DagsterUserCodeUnreachableError` | Code server pod down/restarting |
| `DagsterCodeLocationLoadError`    | Code location failed to load    |
| Timeout / deadline exceeded       | Evaluation took too long        |

### 4. Agent and code server health

```python
mcp__dagster__get_cloud_agents()
```

Check each agent for:

- `status: NOT_RUNNING` or stale `lastHeartbeatTime`
- Non-empty `errors` — includes timestamped `PythonError` entries with stack
  traces (e.g., `DagsterUserCodeUnreachableError` with gRPC connection refused)
- `codeServerStates` with `status: FAILED` — indicates a code location's server
  pod is down, which causes `DagsterUserCodeUnreachableError` in sensor ticks
- `runWorkerStates` with `status: FAILED` — run worker pods that crashed

Agent errors explain downstream symptoms: if a code server is `FAILED`, sensors
for that location will report `DagsterUserCodeUnreachableError`, and runs can't
launch.

### 5. GKE cluster events (requires GKE MCP)

Query `mcp__gke__query_logs` for the time window. Use project `teamster-332318`,
cluster `autopilot-cluster-dagster-hybrid-1`, location `us-central1`.

Run two parallel queries with `severity>=WARNING`:

**Query A** — critical events:

```text
jsonPayload.reason=("ScaleUpFailed" OR "BackoffLimitExceeded" OR "Evicted"
  OR "OOMKilling" OR "Preempted" OR "NodeNotReady")
```

**Query B** — daemon pod health:

```text
jsonPayload.reason="FailedDaemonPod"
```

Summarize Query B by node — a storm of `FailedDaemonPod` events on one node
indicates memory pressure. Don't list every pod.

Format string for both:

```text
{{.timestamp}} {{.jsonPayload.reason}} {{.jsonPayload.involvedObject.kind}}/{{.jsonPayload.involvedObject.name}} {{.jsonPayload.message}}
```

### 6. Correlate and report

Produce a **timeline table** (ET timestamps) combining: run failures, tick
failures, ScaleUpFailed events, evictions, and daemon pod storms.

Then provide:

- **Root cause summary** — group by underlying cause (e.g., "GCE STOCKOUT across
  us-central1-a/b/f", "code error in asset X")
- **Impact** — which assets/jobs affected, whether retries succeeded
- **Action items** — categorized:
  - _No action_: transient, self-resolved via retry
  - _Monitor_: recurring pattern needing attention
  - _Investigate_: requires human follow-up
  - _Escalate_: sustained platform-level problems

Reference
`docs/superpowers/specs/2026-03-27-dagster-gke-best-practices-design.md` when a
proposed solution from that spec addresses an observed failure mode.

## Common mistakes

- Forgetting to convert ET to UTC (ET = UTC-4 during EDT, UTC-5 during EST)
- Only checking failed runs without checking automation ticks — a tick failure
  can silently prevent runs from launching at all
- Listing every `FailedDaemonPod` event individually instead of summarizing by
  node — floods the report with noise
- Not checking if retry runs succeeded — a failure with a successful retry is
  informational, not actionable
