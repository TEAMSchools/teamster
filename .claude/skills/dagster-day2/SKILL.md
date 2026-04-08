---
name: dagster-day2
disable-model-invocation: true
description: >-
  Dagster platform health, run failures, GKE events, tick errors, overnight
  issues. Triggers: "what broke", "cluster healthy", "why did runs fail", "check
  production", or any production status question.
---

# Day-2 Operations Check

## Phase 1: Gather data (Haiku subagent)

Single `model: haiku` Agent call. Compute time window:

- **Default:** 5 PM ET previous business day → now
- **With arg:** `/dagster-day2 24h` (relative) or `/dagster-day2 2026-03-29`
  (absolute, 5 PM ET that date)
- ET = UTC-4 (EDT Mar–Nov) or UTC-5 (EST Nov–Mar). Compute RFC 3339 + epoch.

Replace `{EPOCH}`, `{UTC_START}`, `{UTC_END}`, `{DATE}` below. Run
`mkdir -p dagster-tmp/day2/{DATE}` before dispatching.

```text
Gather Dagster+GCP data. Write each step's JSON to dagster-tmp/day2/{DATE}/
via Write tool. No prose. Classification fields expected.

Parallelization: 1,3,4,5,6,7,8,10,11 independent. 2,9 depend on 1.
3a,3b depend on 3. 4a depends on 4. Fan-out within steps (all get_run_logs
at once, all get_tick_history at once).

## 1. Failed runs

mcp__dagster__list_runs(statuses=["FAILURE"], created_after={EPOCH}).
Paginate if cursor. Collect ALL.

Then IN PARALLEL:
- Per run: mcp__dagster__get_run_logs(run_id=<id>,
    filter_types=["ExecutionStepFailureEvent","RunFailureEvent","EngineEvent"],
    limit=500).
- list_runs(statuses=["SUCCESS"], created_after={EPOCH}, limit=100).
  Paginate to count all.
- list_runs(statuses=["CANCELED"], created_after={EPOCH}, limit=100). Same.

Per failed run: runId, jobName, dagster/code_location, startTime, endTime,
RunFailureEvent message, dagster/will_retry, dagster/auto_retry_run_id.
Totals: failureCount, successCount, canceledCount.

Classify by first match:
  Node OOM/eviction: "low on resource: memory", exit 137, "Evicted"
  Scheduling failure: "FailedScheduling", "Insufficient cpu/memory", taints
  K8s API failure: "DagsterK8sUnrecoverableAPIError"
  Backoff limit: "BackoffLimitExceeded"
  Network/SSH: "ssh:", "SSH tunnel", "port 22", "port 5484"
  Connection failure: "Connection timed out/refused", "gRPC Error code: UNAVAILABLE" (no "ssh:")
  Code error: ExecutionStepFailureEvent with Python traceback
  Infra timeout: "run worker failed" without above signals
  Unclassified: no match — include full message
Add "category" field per run.

## 2. Retry verification (depends on 1)

Skip if no dagster/auto_retry_run_id. Otherwise list_runs(run_ids=<all>).
Collect: runId, status, startTime, endTime. Fetch logs only for FAILURE retries.

## 3. Failed ticks

list_code_locations → names + loadStatus. Per LOADED location IN PARALLEL:
  get_tick_history(name="<loc>__automation_condition_sensor",
    repository_location_name="<loc>", statuses=["FAILURE"], limit=50,
    after_timestamp={EPOCH}).
  list_schedules(repository_location_name="<loc>", schedule_status="RUNNING").

Collect: tickId, timestamp, location, error (300 chars). Extract gRPC IP
("ipv4:<ip>:<port>"). Note locations with 0 failures. Flag non-LOADED for 3a.

For locations with failures, fetch context ticks (ALL statuses):
  get_tick_history(same sensor, after_timestamp=<first_fail - 60>,
    before_timestamp=<last_fail + 60>, limit=50).
Per context tick: timestamp, status, gRPC IP if present. Flat array.

## 3a. Location load failures (depends on 3)

Per non-LOADED location: get_location_load_history(location_name, limit=10).
Collect: locationName, loadStatus, triggerTimestamp, error.

## 3b. Schedule tick failures (depends on 3)

Per RUNNING schedule from step 3 IN PARALLEL:
  get_tick_history(name="<schedule>", repository_location_name="<loc>",
    statuses=["FAILURE"], limit=20, after_timestamp={EPOCH}).
Collect: tickId, timestamp, location, schedule name, error (300 chars).

## 4. Agent health

get_cloud_agents(errors_after={EPOCH}). Extract per agent: id, status,
lastHeartbeatTime, errors (timestamp + message, 300 chars). Discard
codeServerStates/runWorkerStates. Include agents with heartbeat in window +
all RUNNING.

## 4a. Agent pod churn (depends on 4)

Skip if all agents RUNNING with 0 errors. Otherwise count pod creates
(step 6 captures preemption events for all pods):

mcp__gke__query_logs(project_id="teamster-332318",
  query='resource.type="k8s_cluster"
    AND log_name="projects/teamster-332318/logs/events"
    AND resource.labels.cluster_name="autopilot-cluster-dagster-hybrid-1"
    AND jsonPayload.involvedObject.namespace="dagster-cloud"
    AND jsonPayload.involvedObject.name:"user-cloud-dagster-cloud-agent-agent"
    AND jsonPayload.reason="SuccessfulCreate"',
  time_range={startTime: "{UTC_START}", endTime: "{UTC_END}"}, limit=100,
  format="{{.timestamp}} {{.jsonPayload.involvedObject.name}} {{.jsonPayload.message}}").
>4 creates = crash loop or preemption storm (normal: 2 replicas × 2 for rollout).

## 5. Daemon health

get_daemon_health(). Collect: daemonType, healthy. Only include errors if
unhealthy. Skip lastHeartbeatTime (null on Cloud).

## 6. GKE critical events

Two queries IN PARALLEL:

mcp__observability__list_log_entries(
  resourceNames=["projects/teamster-332318"],
  filter='resource.type="k8s_cluster"
    AND log_name="projects/teamster-332318/logs/events"
    AND resource.labels.cluster_name="autopilot-cluster-dagster-hybrid-1"
    AND jsonPayload.involvedObject.namespace="dagster-cloud"
    AND jsonPayload.reason=("ScaleUpFailed" OR "BackoffLimitExceeded"
      OR "NodeNotReady" OR "FailedCreate" OR "FailedScheduling")
    AND timestamp >= "{UTC_START}" AND timestamp <= "{UTC_END}"',
  orderBy="timestamp desc", pageSize=100).

mcp__gke__query_logs(project_id="teamster-332318",
  query='resource.type="k8s_pod"
    AND resource.labels.cluster_name="autopilot-cluster-dagster-hybrid-1"
    AND resource.labels.namespace_name="dagster-cloud"
    AND jsonPayload.reason=("Preempted" OR "Evicted" OR "OOMKilling"
      OR "Preempting" OR "BackOff")',
  time_range={startTime: "{UTC_START}", endTime: "{UTC_END}"}, limit=100,
  format="{{.timestamp}} {{.resource.labels.pod_name}} {{.jsonPayload.reason}} {{.jsonPayload.message}}").

Per entry: timestamp, reason, pod/object name, message. Flag truncation.

## 7. Alerts

Two calls IN PARALLEL:
  list_alerts(parent="projects/teamster-332318", filter='state="OPEN"').
  list_alerts(parent="projects/teamster-332318",
    filter='open_time >= "{UTC_START}"', orderBy="open_time desc", pageSize=50).
Deduplicate. Per alert: name, displayName, state, open_time, close_time,
resource labels, metric type, policy. Pod type from name:
  dagster-step-* → step worker, dagster-run-* → run coordinator,
  <loc>-prod-* → code server.

## 8. Error groups

list_group_stats(projectName="projects/teamster-332318",
  timeRangePeriod="PERIOD_1_DAY", order="COUNT_DESC", pageSize=10).
Per group: ID, count, exception (300 chars), services.

## 9. OOM drill-down (depends on 1)

Skip if no "Node OOM/eviction" runs. Per OOM run:
list_time_series(name="projects/teamster-332318",
  filter='metric.type="kubernetes.io/container/memory/used_bytes"
    AND resource.labels.pod_name=starts_with("<prefix>")',
  interval={startTime: "<run_start-5m>", endTime: "<run_end+5m>"},
  aggregation={alignmentPeriod: "60", perSeriesAligner: "ALIGN_MAX"}).
Pod prefix: <loc>-prod-* (code server), dagster-run-* (coordinator),
dagster-step-* (step). Collect: peak bytes, limit bytes.

## 10. Queued/stuck runs

list_runs(statuses=["QUEUED","NOT_STARTED","MANAGED","STARTING"],
  created_after={EPOCH}, limit=20).
Flag runs queued >15 min. Collect: runId, jobName, status, startTime, duration.

## 11. Backfills

IN PARALLEL: list_backfills(status="REQUESTED", limit=10),
list_backfills(status="FAILED", created_after={EPOCH}, limit=10).
Collect: backfillId, status, numPartitions, timestamp, error.

Write JSON to dagster-tmp/day2/{DATE}/:
  step-1-failed-runs.json, step-2-retries.json, step-3-ticks.json,
  step-3a-load-failures.json, step-3b-schedule-ticks.json,
  step-4-agents.json, step-4a-agent-pod-churn.json,
  step-5-daemons.json, step-6-gke-events.json,
  step-7-alerts.json, step-8-error-groups.json, step-9-oom-metrics.json,
  step-10-queued-runs.json, step-11-backfills.json.
Skip empty steps. Return JSON manifest: {filename: absolute_path}.
```

## Phase 2: Correlate and report

Read from `dagster-tmp/day2/{DATE}/` per manifest.

**Temporal overlap gate**: Before linking signals as cause/effect, verify
`max(start_A, start_B) < min(end_A, end_B)`. If false → independent findings.

**Reclassify** runs using cross-signal context:

- "Unclassified"/"Connection failure" → "Agent API timeout" if agent errors show
  "ReadTimeout" + `*.agent.dagster.cloud` in same window.
- Override wrong categories (e.g. "Code error" that's actually K8s API timeout).
- New OOM runs → pull memory metrics per step 9.

**Deploy rollover**: gRPC UNAVAILABLE ticks in brief clusters bounded by
successes + IP change between clusters = code server pod replacement. Report
per-cluster duration (consecutive failures × ~30s), not first-to-last span.

**Agent topology**: Steady state = 2 RUNNING. Flag deviations. Cross-reference
step 6 pod events filtered to `user-cloud-dagster-cloud-agent-agent` for cause
(Preempted/Evicted/OOMKilling). Step 4a churn: 2–4 creates = one-off, >>4 =
sustained storm.

**Timeline table** (ET): run failures, tick failures, schedule tick failures,
location load failures, agent errors, code server failures, unhealthy daemons,
GKE events, alerts, error groups.

**Report format:**

```markdown
## Day-2 Operations Report — {DATE_RANGE}

**Run volume:** {success} succeeded, {failure} failed, {canceled} canceled

### Timeline (ET)

| Time | Signal | Source |
| ---- | ------ | ------ |

### Root Causes

**1. {title}** {Narrative linking signals.}

### Impact

- **Run failures:** ...
- **Tick failures:** ...
- **Schedule tick failures:** ... (omit if none)
- **Alerts:** ... (omit if none)
- **Queued runs:** ... (omit if none)
- **Backfills:** ... (omit if none)

### Emerging Issues

{Omit if no error groups.}

### Actions

| Action | Item | Rationale |
| ------ | ---- | --------- |
```

**Root causes**: Group by underlying cause. Link location load failures → tick
outages, agent errors → tick failures, daemon issues → tick/run impacts, alerts
→ correlated failures. GKE infra pod events are first-class findings:

- `user-cloud-dagster-cloud-agent-agent` → global scheduling/sensor impact
- `onepassword-connect*` → secret injection for new pods broken
- `<loc>-prod-*` → per-location sensor/schedule outage

**Impact**: Affected assets/jobs, retry outcomes (definitive). Include queued
runs and backfills if present.

**Emerging issues**: Error groups not yet causing failures but increasing. Omit
if none.

**Actions**: No action (transient + retry success), Monitor
(recurring/emerging), Investigate (retry failure), Escalate (sustained platform
issue).

Flag truncation if any query hit pagination limits.

Reference `.k8s/CLAUDE.md` for scheduling, topology, security, config.

Write report to `dagster-tmp/day2/{DATE}/report.md`.
