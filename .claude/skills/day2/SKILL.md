---
name: day2
disable-model-invocation: true
description: >-
  Use when checking Dagster platform health, triaging run failures,
  investigating GKE cluster events, reviewing sensor tick errors, or diagnosing
  overnight batch issues. Trigger on any question about what failed, what's
  unhealthy, or what happened in production — not just scheduled morning checks.
  Also use when the user says things like "what broke overnight", "is the
  cluster healthy", "why did runs fail", or "check production status".
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
Gather Dagster and GCP Observability data. Return structured JSON only — no
prose, recommendations, or narrative. Classification fields are expected.

Steps 1, 3, 4, 5, 6, 7, and 8 are independent -- call their initial tools in
parallel. Steps 2 and 9 depend on step 1's output. Step 3a depends on step 3's
output. Within steps 1 and 3, parallelize fan-out calls (e.g. all get_run_logs
calls at once, all list_sensors calls at once, all get_tick_history calls at
once).

## 1. Failed runs

mcp__dagster__list_runs(statuses=["FAILURE"], created_after={EPOCH}).
For each run IN PARALLEL: mcp__dagster__get_run_logs(run_id=<id>,
  filter_types=["ExecutionStepFailureEvent","RunFailureEvent","EngineEvent"],
  limit=500).
Collect: runId, jobName, dagster/code_location tag, startTime, endTime,
RunFailureEvent message, dagster/will_retry value, dagster/auto_retry_run_id.
Classify each run by first matching signal (using run logs only):
  Node OOM/eviction: "low on resource: memory", exit 137, "Evicted"
  Scheduling failure: "FailedScheduling", "Insufficient cpu/memory", taints
  K8s API failure: "K8s API failure", "DagsterK8sUnrecoverableAPIError"
  Backoff limit: "Job has reached the specified backoff limit", "BackoffLimitExceeded"
  Network/SSH: "ssh:", "SSH tunnel", "port 22", "port 5484"
  Connection failure: "Connection timed out/refused", "gRPC Error code: UNAVAILABLE" (no "ssh:")
  Code error: ExecutionStepFailureEvent with Python traceback
  Infra timeout: "run worker failed" without scheduling/OOM/K8s API signals
  Unclassified: no match -- include full message
Include a "category" field on each run.

## 2. Retry verification (depends on step 1)

Skip if no runs have dagster/auto_retry_run_id. Otherwise call
mcp__dagster__list_runs with run_ids=<all autoRetryRunId values>.
Collect: runId, status, startTime, endTime. Only fetch logs (same filter_types)
for retries with status FAILURE.

## 3. Failed ticks

mcp__dagster__list_code_locations for location names and load status. Then IN
PARALLEL for each loaded location:
  mcp__dagster__list_sensors(repository_location_name="<loc>")
to discover sensor names. Then IN PARALLEL for each automation sensor
(sensorType="AUTOMATION"):
mcp__dagster__get_tick_history(
  name="<sensor_name>",
  repository_location_name="<loc>", statuses=["FAILURE"], limit=50,
  after_timestamp={EPOCH}).
Collect: tickId, timestamp, location, sensor name, error message (first 300
chars). Report which locations returned 0 in-window failures (confirm all were
queried). If a location has loadStatus != "LOADED", skip tick queries for it and
flag it for step 3a.

## 3a. Code location load failures (depends on step 3)

For each location with loadStatus != "LOADED" from step 3:
mcp__dagster__get_location_load_history(location_name="<loc>", limit=10).
Collect: locationName, loadStatus, codeLocationUpdateTriggerTimestamp, error
message. This shows the deploy timeline — when the location broke and whether
prior deploys loaded successfully.

## 4. Agent health

mcp__dagster__get_cloud_agents(). Response is very large (200KB+) and WILL be
saved to a file. You MUST run the filter script on the saved file:
  uv run python .claude/skills/day2/filter_agents.py <FILE_PATH> {EPOCH}
The file path appears in the tool result (look for a path ending in .txt).
Use the script output directly — do not parse the raw file yourself.
Per agent the script returns: id, status, lastHeartbeatTime, filtered errors
(timestamp + message, truncated to 300 chars), codeServerStates, runWorkerStates.

## 5. Daemon health

mcp__dagster__get_daemon_health(). Collect daemonType and healthy (true/false).
Only include lastHeartbeatErrors if unhealthy. Skip lastHeartbeatTime (always
null on Dagster Cloud).

## 6. GKE critical events (Cloud Logging)

mcp__observability__list_log_entries(
  resourceNames=["projects/teamster-332318"],
  filter='resource.type="k8s_cluster"
    AND log_name="projects/teamster-332318/logs/events"
    AND resource.labels.cluster_name="autopilot-cluster-dagster-hybrid-1"
    AND jsonPayload.involvedObject.namespace="dagster-cloud"
    AND jsonPayload.reason=("ScaleUpFailed" OR "BackoffLimitExceeded"
      OR "Evicted" OR "OOMKilling" OR "Preempted" OR "NodeNotReady"
      OR "FailedCreate" OR "FailedScheduling")
    AND timestamp >= "{UTC_START}" AND timestamp <= "{UTC_END}"',
  orderBy="timestamp desc",
  pageSize=100).
Collect per entry: timestamp, jsonPayload.reason, involvedObject kind+name,
message. If the response includes a nextPageToken, add "truncated": true.

## 7. Open alerts (Cloud Monitoring)

mcp__observability__list_alerts(
  parent="projects/teamster-332318",
  filter='state="OPEN"').
Collect per alert: name, displayName, state, open_time, policy name/ID,
condition display name. If no alerts are open, return an empty array.

## 8. Recurring error groups (Error Reporting)

mcp__observability__list_group_stats(
  projectName="projects/teamster-332318",
  timeRangePeriod="PERIOD_1_DAY",
  order="COUNT_DESC",
  pageSize=10).
Collect per group: group ID, count, representative exception message (first
300 chars), affected services. If no groups are returned, return an empty array.

## 9. OOM memory drill-down (depends on step 1)

For each run classified as "Node OOM/eviction", pull container memory to
quantify the spike:
mcp__observability__list_time_series(
  name="projects/teamster-332318",
  filter='metric.type="kubernetes.io/container/memory/used_bytes"
    AND resource.labels.pod_name=starts_with("<pod-prefix>")',
  interval={startTime: "<run_start_minus_5m>", endTime: "<run_end_plus_5m>"},
  aggregation={alignmentPeriod: "60", perSeriesAligner: "ALIGN_MAX"}).
Extract the pod name prefix from the run's tags or logs. Pod naming by type:
  Code server: <location>-prod-* (e.g. kippnewark-prod-abc12-xyz)
  Run coordinator: dagster-run-*
  Step worker: dagster-step-*
Use starts_with("<location>-") for code server pods (e.g.
starts_with("kippnewark-")) or starts_with("dagster-run-") for run pods.
Check run worker logs for the exact pod name if the tag is ambiguous.
Collect per run: peak memory bytes, memory limit bytes. Skip this step if no
runs are classified as "Node OOM/eviction".

Return JSON with keys: failed_runs, retry_outcomes, failed_ticks,
location_load_failures, agents, daemon_health, gke_critical_events, open_alerts,
error_groups, oom_metrics.
```

## Phase 2: Correlate and report

Runs arrive pre-classified from Phase 1 (each has a `category` field). Verify
and refine classifications using cross-signal context now available:

- Reclassify "Unclassified" or "Connection failure" runs as "Agent API timeout"
  if agent errors (step 4) show "ReadTimeout" + `*.agent.dagster.cloud` in the
  same time window.
- Override any other category that is clearly wrong given the full picture (e.g.
  a run classified "Code error" whose traceback is actually a K8s API timeout).
- If reclassification creates new "Node OOM/eviction" runs that Haiku missed,
  pull their memory metrics using the same `list_time_series` query from step 9.

**Timeline table** (ET): combine run failures, tick failures, code location load
failures, agent errors, code server failures, unhealthy daemons, GKE critical
events (ScaleUpFailed, evictions, OOM), open alerts, and top error groups.

**Report sections:**

- **Root causes** -- group by underlying cause; link code location load failures
  to tick outages (a location in ERROR state means its sensors can't evaluate);
  link agent code server errors to tick failures; link daemon issues to tick/run
  impacts; link open alerts to correlated run/tick failures. GKE events on infra
  pods are first-class findings — surface them even when no run or tick failed:
  - `user-cloud-dagster-cloud-agent-agent` — agent eviction/OOM impacts all
    scheduling and sensor evaluation until a replacement pod is ready.
  - `onepassword-connect`, `onepassword-connect-operator` — eviction/restart
    breaks secret injection for new pods; existing pods are unaffected.
  - `<location>-prod-*` — code server eviction/OOM causes sensor and schedule
    outages for that location until Dagster Cloud reconciles a replacement.

  Correlate all infra pod events with agent health and daemon data.

- **Impact** -- affected assets/jobs, retry outcomes (definitive, not guesses).
- **Emerging issues** -- recurring error groups from Error Reporting that have
  not yet caused run failures but show increasing frequency. Omit this section
  if no error groups were returned.
- **Actions** -- _No action_ (transient, cite retry success), _Monitor_
  (recurring pattern or emerging error group), _Investigate_ (needs human, cite
  retry failure), _Escalate_ (sustained platform problems or open alerts).
- **Truncation warning** if any log query returned a nextPageToken.

Reference `.k8s/CLAUDE.md` for scheduling strategy, topology spread, security
contexts, and config restrictions.
