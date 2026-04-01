---
name: day2
description: >-
  Use when performing daily platform health checks, triaging overnight Dagster
  run failures, investigating GKE cluster events, or reviewing automation sensor
  tick errors. Invoke at start of workday or after overnight batch windows.
---

# Day-2 Operations Check

## Phase 1: Gather data (Haiku subagent)

Compute the time window, then dispatch a **single** `model: haiku` Agent call.

- **Default:** 5 PM ET previous business day to now.
- **With argument:** `/day2 24h` (relative) or `/day2 2026-03-29` (absolute, 5
  PM ET that date).
- ET = UTC-4 (EDT, Mar-Nov) or UTC-5 (EST, Nov-Mar). Compute RFC 3339 UTC and
  Unix epoch.

Replace `{EPOCH}`, `{UTC_START}`, `{UTC_END}` in the prompt below.

```text
Gather Dagster and GKE data. Return ONLY raw JSON, no analysis.

Steps 1, 3, 4, 5, and 6 are independent -- call their initial tools in parallel.
Step 2 depends on step 1's output. Within steps 1 and 3, parallelize fan-out
calls (e.g. all get_run_logs calls at once, all get_tick_history calls at once).

## 1. Failed runs

mcp__dagster__list_runs(statuses=["FAILURE"], created_after={EPOCH}).
For each run IN PARALLEL: mcp__dagster__get_run_logs(run_id=<id>,
  filter_types=["ExecutionStepFailureEvent","RunFailureEvent","EngineEvent"],
  limit=500).
Collect: runId, jobName, dagster/code_location tag, startTime, endTime,
RunFailureEvent message, dagster/will_retry value, dagster/auto_retry_run_id.

## 2. Retry verification (depends on step 1)

Call mcp__dagster__list_runs with run_ids=<all autoRetryRunId values>.
Collect: runId, status, startTime, endTime. Only fetch logs (same filter_types)
for retries with status FAILURE.

## 3. Failed ticks

mcp__dagster__list_code_locations for location names. Then IN PARALLEL for each:
mcp__dagster__get_tick_history(
  name="<loc>__automation_condition_sensor",
  repository_location_name="<loc>", statuses=["FAILURE"], limit=50).
Response is often saved to a file (too large for context). Check each tool
result — if it mentions a file path (ending in .txt), you MUST run:
  python3 .claude/skills/day2/filter_ticks.py <FILE_PATH> {EPOCH}
Use the script output directly. If the result is inline (no file path), discard
ticks with timestamp < {EPOCH} (verify numerically).
Collect: tickId, timestamp, location, error message (first 300 chars).
Report which locations returned 0 in-window failures (confirm all were queried).

## 4. Agent health

mcp__dagster__get_cloud_agents(). Response is very large (200KB+) and WILL be
saved to a file. You MUST run the filter script on the saved file:
  python3 .claude/skills/day2/filter_agents.py <FILE_PATH> {EPOCH}
The file path appears in the tool result (look for a path ending in .txt).
Use the script output directly — do not parse the raw file yourself.
Per agent the script returns: id, status, lastHeartbeatTime, filtered errors
(timestamp + message, truncated to 300 chars), codeServerStates, runWorkerStates.

## 5. Daemon health

mcp__dagster__get_daemon_health(). Collect daemonType and healthy (true/false).
Only include lastHeartbeatErrors if unhealthy. Skip lastHeartbeatTime (always
null on Dagster Cloud).

## 6. GKE events

Two PARALLEL mcp__gke__query_logs calls: project=teamster-332318,
cluster=autopilot-cluster-dagster-hybrid-1, location=us-central1,
time_range={{"start_time":"{UTC_START}","end_time":"{UTC_END}"}}, limit=100.
Read .claude/skills/day2/gke_log_format.txt and pass its contents as the format
parameter verbatim. The response will be formatted text lines, not JSON — return
them as-is in an array of strings (one per log line).

Query A filter (critical):
  resource.type="k8s_cluster"
  log_name="projects/teamster-332318/logs/events"
  resource.labels.cluster_name="autopilot-cluster-dagster-hybrid-1"
  jsonPayload.reason=("ScaleUpFailed" OR "BackoffLimitExceeded" OR "Evicted"
    OR "OOMKilling" OR "Preempted" OR "NodeNotReady")

Query B filter (daemon pods): same resource/log/cluster filters with
  jsonPayload.reason="FailedDaemonPod"
Count per node name, not individual pods.

If either query returns exactly 100 results, add "truncated": true.

Return JSON with keys: failed_runs, retry_outcomes, failed_ticks, agents,
daemon_health, gke_critical_events, gke_daemon_pod_storms.
```

## Phase 2: Classify and correlate

**Classify each failed run** by first matching signal:

| Category           | Signals                                                                    |
| ------------------ | -------------------------------------------------------------------------- |
| Node OOM/eviction  | "low on resource: memory", exit 137, "Evicted"                             |
| Scheduling failure | "FailedScheduling", "Insufficient cpu/memory", taints                      |
| K8s API failure    | "K8s API failure", "DagsterK8sUnrecoverableAPIError"                       |
| Backoff limit      | "Job has reached the specified backoff limit", "BackoffLimitExceeded"      |
| Network/SSH        | "ssh:", "SSH tunnel", "port 22", "port 5484"                               |
| Connection failure | "Connection timed out/refused", "gRPC Error code: UNAVAILABLE" (no "ssh:") |
| Code error         | ExecutionStepFailureEvent with Python traceback                            |
| Infra timeout      | "run worker failed" without scheduling/OOM/K8s API signals                 |
| Unclassified       | No match -- include full message, flag for review                          |

**Timeline table** (ET): combine run failures, tick failures, agent errors, code
server failures, unhealthy daemons, ScaleUpFailed, evictions, daemon pod storms.

**Report sections:**

- **Root causes** -- group by underlying cause; link agent code server errors to
  tick failures; link daemon issues to tick/run impacts.
- **Impact** -- affected assets/jobs, retry outcomes (definitive, not guesses).
- **Actions** -- _No action_ (transient, cite retry success), _Monitor_
  (recurring pattern), _Investigate_ (needs human, cite retry failure),
  _Escalate_ (sustained platform problems).
- **Truncation warning** if any GKE query hit 100 results.

Reference `.k8s/CLAUDE.md` for scheduling strategy, topology spread, security
contexts, and config restrictions.
