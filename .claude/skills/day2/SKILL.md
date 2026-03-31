---
name: day2
description: >-
  Use when performing daily platform health checks, triaging overnight Dagster
  run failures, investigating GKE cluster events, or reviewing automation sensor
  tick errors. Invoke at start of workday or after overnight batch windows.
---

# Day-2 Operations Check

Triage overnight platform health across Dagster+, GKE Autopilot, and automation
sensors. Dispatches a Haiku subagent for data gathering, then synthesizes.

## Phase 1: Gather data (Haiku subagent)

Compute the time window before dispatching. Default: 5 PM ET previous business
day to now. ET = UTC-4 (EDT, Mar–Nov) or UTC-5 (EST, Nov–Mar). Convert to both
RFC 3339 UTC and Unix epoch.

Dispatch a **single** Agent call with `model: haiku` and the prompt below.
Replace `{EPOCH}`, `{UTC_START}`, and `{UTC_END}` with computed values.

```text
Gather Dagster and GKE operational data. Return ONLY raw JSON — no analysis.

## 1. Failed runs

Call mcp__dagster__list_runs(statuses=["FAILURE"], created_after={EPOCH}).

For each run, call mcp__dagster__get_run_logs(run_id=<id>,
  filter_types=["ExecutionStepFailureEvent","RunFailureEvent","EngineEvent"],
  limit=500).

Collect per run: runId, jobName, code location (from dagster/code_location tag),
startTime, endTime, the RunFailureEvent message, whether dagster/will_retry is
"true", and the dagster/auto_retry_run_id value if present.

## 2. Failed automation ticks

Call mcp__dagster__list_code_locations to get all location names.

For each location, call mcp__dagster__get_tick_history(
  name="<location>__automation_condition_sensor",
  repository_location_name="<location>",
  statuses=["FAILURE"], limit=20).

Keep only ticks with timestamp >= {EPOCH}. Collect per tick: tickId, timestamp,
location, error message (first 300 chars).

## 3. Agent health

Call mcp__dagster__get_cloud_agents().

Collect per agent: id, agentLabel, status, lastHeartbeatTime. For each entry in
errors: timestamp and error.message. For each codeServerState: locationName,
status, error.message if present. For each runWorkerState: runId, status,
message.

## 4. GKE cluster events

Run TWO parallel mcp__gke__query_logs calls for project teamster-332318, cluster
autopilot-cluster-dagster-hybrid-1, location us-central1, time_range
{{"start_time":"{UTC_START}","end_time":"{UTC_END}"}}, limit 100, format
"{{{{.timestamp}}}} {{{{.jsonPayload.reason}}}} {{{{.jsonPayload.involvedObject.kind}}}}/{{{{.jsonPayload.involvedObject.name}}}} {{{{.jsonPayload.message}}}}":

Query A (critical):
  resource.type="k8s_cluster"
  log_name="projects/teamster-332318/logs/events"
  resource.labels.cluster_name="autopilot-cluster-dagster-hybrid-1"
  jsonPayload.reason=("ScaleUpFailed" OR "BackoffLimitExceeded" OR "Evicted"
    OR "OOMKilling" OR "Preempted" OR "NodeNotReady")

Query B (daemon pods):
  resource.type="k8s_cluster"
  log_name="projects/teamster-332318/logs/events"
  resource.labels.cluster_name="autopilot-cluster-dagster-hybrid-1"
  jsonPayload.reason="FailedDaemonPod"

For Query B, count events per node name — do NOT list individual pods.

Return all collected data as a single JSON object with keys: failed_runs,
failed_ticks, agents, gke_critical_events, gke_daemon_pod_storms.
```

## Phase 2: Classify and correlate

Using the subagent's returned data:

**Classify each failed run:**

| Category            | Signals                                               |
| ------------------- | ----------------------------------------------------- |
| Node OOM / eviction | "low on resource: memory", exit 137, "Evicted"        |
| Scheduling failure  | "FailedScheduling", "Insufficient cpu/memory", taints |
| Code error          | `ExecutionStepFailureEvent` with Python traceback     |
| Infra timeout       | "run worker failed" without scheduling/OOM signals    |

**Produce a timeline table** (ET timestamps) combining: run failures, tick
failures, agent errors, code server failures, ScaleUpFailed events, evictions,
and daemon pod storms.

**Report:**

- **Root cause summary** — group by underlying cause (e.g., "GCE STOCKOUT across
  us-central1-a/b/f", "code error in asset X"). Link agent code server failures
  to corresponding tick failures.
- **Impact** — which assets/jobs affected, whether retries succeeded
- **Action items** — categorized:
  - _No action_: transient, self-resolved via retry
  - _Monitor_: recurring pattern needing attention
  - _Investigate_: requires human follow-up
  - _Escalate_: sustained platform-level problems

Reference
`docs/superpowers/specs/2026-03-27-dagster-gke-best-practices-design.md` when a
proposed solution from that spec addresses an observed failure mode.
