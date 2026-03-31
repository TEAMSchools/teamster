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

Compute the time window before dispatching:

- **Default:** 5 PM ET previous business day → now.
- **With argument:** `/day2 24h` (relative duration), `/day2 2026-03-29`
  (absolute start date, uses 5 PM ET on that date).
- ET = UTC-4 (EDT, Mar–Nov) or UTC-5 (EST, Nov–Mar). Convert to both RFC 3339
  UTC and Unix epoch.

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

## 2. Retry outcome verification

Collect all autoRetryRunId values from step 1. Call mcp__dagster__list_runs with
run_ids set to that list. For each retry run, collect: runId, status, startTime,
endTime. Do NOT fetch logs for retry runs unless their status is FAILURE — if a
retry also failed, fetch its logs with the same filter_types as step 1.

## 3. Failed automation ticks

Call mcp__dagster__list_code_locations to get all location names.

For each location, call mcp__dagster__get_tick_history(
  name="<location>__automation_condition_sensor",
  repository_location_name="<location>",
  statuses=["FAILURE"], limit=20).

Keep only ticks with timestamp >= {EPOCH}. Collect per tick: tickId, timestamp,
location, and the error message. Extract the error from the tick's `error` field
(or `error.message` if nested). Truncate to the first 300 characters. If the
error field is null or missing, set errorMessage to "no error details returned".

## 4. Agent health

Call mcp__dagster__get_cloud_agents().

Collect per agent: id, agentLabel, status, lastHeartbeatTime. For each entry in
errors: timestamp and error.message. For each codeServerState: locationName,
status, error.message if present. For each runWorkerState: runId, status,
message.

## 5. Daemon health

Call mcp__dagster__get_daemon_health().

Collect per daemon: daemonType, healthy, lastHeartbeatTime. If any daemon is
unhealthy, include its lastHeartbeatErrors.

## 6. GKE cluster events

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

For BOTH queries: if the result contains exactly `limit` entries (100), add
`"truncated": true` to that key in the output so Phase 2 knows data is
incomplete.

Return all collected data as a single JSON object with keys: failed_runs,
retry_outcomes, failed_ticks, agents, daemon_health, gke_critical_events,
gke_daemon_pod_storms.
```

## Phase 2: Classify and correlate

Using the subagent's returned data:

**Classify each failed run:**

| Category            | Signals                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------- |
| Node OOM / eviction | "low on resource: memory", exit 137, "Evicted"                                                       |
| Scheduling failure  | "FailedScheduling", "Insufficient cpu/memory", taints                                                |
| K8s API failure     | "K8s API failure", "DagsterK8sUnrecoverableAPIError", "Unexpected error encountered in Kubernetes"   |
| Backoff limit       | "Job has reached the specified backoff limit", "BackoffLimitExceeded"                                |
| Network / SSH       | "ssh:", "SSH tunnel", "port 22", "port 5484"                                                         |
| Connection failure  | "Connection timed out", "Connection refused", "gRPC Error code: UNAVAILABLE" (without "ssh:")        |
| Code error          | `ExecutionStepFailureEvent` with Python traceback                                                    |
| Infra timeout       | "run worker failed" without scheduling/OOM/K8s API signals                                           |
| **Unclassified**    | No signals above matched — include full failure message in report and flag for classification review |

**Produce a timeline table** (ET timestamps) combining: run failures, tick
failures, agent errors, code server failures, daemon health issues,
ScaleUpFailed events, evictions, and daemon pod storms.

**Report:**

- **Root cause summary** — group by underlying cause (e.g., "GCE STOCKOUT across
  us-central1-a/b/f", "code error in asset X"). Link agent code server failures
  to corresponding tick failures. Link daemon health issues to tick/run impacts.
- **Impact** — which assets/jobs affected, and whether retries succeeded or
  failed (use retry_outcomes data — report definitive status, not guesses)
- **Action items** — categorized:
  - _No action_: transient, self-resolved via retry (cite retry success)
  - _Monitor_: recurring pattern needing attention
  - _Investigate_: requires human follow-up (cite retry failure if applicable)
  - _Escalate_: sustained platform-level problems
- **Truncation warning** — if any GKE query was truncated, note it and suggest
  narrowing the time window or re-running with a filter

When an observed failure mode maps to a solution in the GKE best practices
hardening spec (branch `cbini/docs/claude-dagster-gke-best-practices`, file
`docs/superpowers/specs/2026-03-27-dagster-gke-best-practices-design.md`),
reference the specific spec section (e.g., "Spec Section 1: Agent Resilience —
topology spread would reduce correlated zone preemption risk").
