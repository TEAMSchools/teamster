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

Replace `{EPOCH}`, `{UTC_START}`, `{UTC_END}` below. Run
`rm -rf .claude/scratch/day2` before dispatching — each invocation starts from
an empty directory (the Write tool recreates it).

```text
Gather Dagster+GCP data. Write each step's JSON to .claude/scratch/day2/
via Write tool. No prose. Classification fields expected.

Parallelization: 1,3,4,7,9,10,11,12,14,15 independent. 2,13 depend on 1.
5,6 depend on 3. 8 depends on 7. Fan-out within steps (all get_run_logs at
once, all get_tick_history at once).

## Pagination contract (MANDATORY for every step)

If any list/query returns the page size you requested, the result is
PRESUMPTIVELY TRUNCATED. You MUST loop until a page returns FEWER than the
requested limit. Do not write the file until pagination terminates. Failing
to paginate is a critical bug — do not skip even if you think the result
is complete.

Each per-step JSON MUST include a top-level field:
  "pagination": {"pages": N, "lastPageSize": M, "limit": L, "complete": M < L}
If complete=false you have a bug — loop more. For steps with multiple
paginated sub-queries (step 1: failure/success/canceled), emit one
pagination object per sub-query keyed by status.

Page-cursor patterns:
- list_runs / list_backfills / get_tick_history: pass cursor or use
  before_timestamp=<oldest_returned - 1> for the next page
- mcp__gke__query_logs / mcp__observability__list_log_entries: use the
  OLDEST returned timestamp as the next time_range.start_time (results
  returned ascending)
- list_alerts / list_group_stats: nextPageToken

Individual steps below do NOT re-explain pagination — they only note the
limit and any step-specific cursor quirks. The global contract applies
unconditionally.

## 1. Failed runs

list_runs(statuses=["FAILURE"], created_after={EPOCH}, limit=100). Paginate
per contract. Collect ALL.

Then IN PARALLEL:
- Per run: get_run_logs(run_id=<id>,
    filter_types=["ExecutionStepFailureEvent","RunFailureEvent","EngineEvent"],
    limit=500).
- list_runs(statuses=["SUCCESS"], created_after={EPOCH}, limit=25). Paginate
  and sum into a count. Write ONLY
  {count: N, pages: P, lastPageSize: M, complete: M<25} — NOT the full run
  list (response exceeds token limit at higher page sizes). Full run details
  (asset selections, tags, step stats) are ~1.5KB each.
- list_runs(statuses=["CANCELED"], created_after={EPOCH}, limit=25). Same
  count-only treatment.

Per failed run: runId, jobName, dagster/code_location, startTime, endTime,
RunFailureEvent message, dagster/will_retry, dagster/auto_retry_run_id.
Totals: failureCount, successCount, canceledCount.

`step-1-failed-runs.json` top-level shape:
  {
    "failureCount": N, "failures": [...],
    "successCount": N,
    "canceledCount": N,
    "pagination": {
      "failure":  {pages, lastPageSize, limit: 100, complete},
      "success":  {pages, lastPageSize, limit: 25, complete},
      "canceled": {pages, lastPageSize, limit: 25, complete}
    }
  }

Classify by the FIRST rule that matches, checked in this order. The error
CLASS (first line of error.message) takes precedence over the stack trace —
a traceback that passes through `ssh_resource`
(`src/teamster/libraries/powerschool/sis/odbc/resources.py`) or
`k8s_client` does NOT mean network or API failure; the caller's class name
is what matters.

  Preemption/Interrupt: error class `DagsterExecutionInterruptedError`
    OR EngineEvent message "Step execution terminated by interrupt"
    OR EngineEvent message "received SIGTERM"
  Node OOM/eviction: "low on resource: memory", exit 137, "Evicted"
  Scheduling failure: "FailedScheduling", "Insufficient cpu/memory", taints
  K8s API failure: error class `DagsterK8sUnrecoverableAPIError`
  Backoff limit: "BackoffLimitExceeded"
  Network/SSH: error class `paramiko.*`, `socket.timeout`, `OSError: [Errno`,
    or explicit "SSH tunnel failed"/"port 22"/"port 5484" in the error
    message (NOT just the stack) — stack traces through ssh_resource.py do
    NOT count; they're incidental when a step gets interrupted mid-call
  Connection failure: error class starts with "grpc." OR
    "gRPC Error code: UNAVAILABLE" in message (no Interrupt signal above)
  Code error: ExecutionStepFailureEvent with Python traceback AND no
    Interrupt signal above
  Infra timeout: "run worker failed" without any above signals
  Unclassified: no match — include full message AND first 3 stack frames
Add "category" field per run.

Cross-reference rule (run in Phase 2, NOT Phase 1): if a run classified as
Preemption/Interrupt has a startTime..endTime window that contains a
`Preempted` event for a pod matching `dagster-step-<md5>-*` or
`dagster-run-*` from step 6, note that the pod preemption IS the cause —
they are the same event, not two correlated findings. Match by (a) the
pod preemption timestamp falling within the run window AND (b) the
EngineEvent "Step execution terminated by interrupt" timestamp within ±2s
of the pod Preempted timestamp.

## 2. Retry verification (depends on 1)

Skip if no dagster/auto_retry_run_id. Otherwise list_runs(run_ids=<all>).
Collect: runId, status, startTime, endTime. Fetch logs only for FAILURE retries.

CRITICAL: `list_runs(run_ids=...)` status can disagree with the run's event
log. For every retry (not just FAILURE), fetch the terminal event via
`get_run_logs(run_id=<id>,
filter_types=["RunSuccessEvent","RunFailureEvent"], limit=5)`. If the
terminal event is `RunFailureEvent`, record retryStatus=FAILURE regardless
of what list_runs reported, and fetch the full failure logs. Phase 2
depends on accurate retry outcomes — a retry silently reported as non-
FAILURE while its event log ends in RunFailureEvent will point root-cause
analysis in the wrong direction.

MANDATORY: every retry entry MUST have retryStatus ∈ {SUCCESS, FAILURE}.
"UNKNOWN", null, or missing is a bug — re-query list_runs AND get_run_logs
for that runId before writing. The validation block below rejects any
other value.

## 3. Failed sensor ticks

list_code_locations → names + loadStatus.

Per LOADED location IN PARALLEL:
  list_sensors(repository_location_name="<loc>", sensor_status="RUNNING") →
    collect ALL sensor names (AUTO_MATERIALIZE and STANDARD types).
  list_schedules(repository_location_name="<loc>", schedule_status="RUNNING") →
    collect schedule names (used in step 6).

CRITICAL: do NOT hardcode `<loc>__automation_condition_sensor` or any other
sensor name. A location has one automation-condition sensor plus many
STANDARD sensors (SFTP, Google Sheets, BigQuery, forms, Couchdrop, etc.).
Missing any of them means missing failures — e.g., a STANDARD sensor stuck
for 10 h on `DagsterUnknownPartitionError` will be invisible if only the
automation sensor is queried.

Then IN PARALLEL across all (location, sensor) pairs:
  get_tick_history(name="<sensor>", repository_location_name="<loc>",
    statuses=["FAILURE"], limit=100, after_timestamp={EPOCH}). Paginate per
  contract; cursor is before_timestamp=<oldest_returned - 1>.

A single sensor with 60+ failures can blow the tool-result token budget. If
a single get_tick_history page exceeds the token limit, the tool will error
with a file path — read with jq and extract only tickId/timestamp/error
(first 300 chars), discarding stack frames.

Collect per failure tick: tickId, timestamp, location, sensorName,
sensorType (AUTO_MATERIALIZE or STANDARD), grpcIp (extracted from
"ipv4:<ip>:<port>" if present in error — mostly relevant for
AUTO_MATERIALIZE sensors, STANDARD sensor failures rarely have gRPC IPs),
error (300 chars, first-line class + first exception message). Note
locations with 0 failures across all sensors. Flag non-LOADED for step 5.

Per sensor write ALL failure ticks as an array (not count + sample).
CRITICAL: write every tick — do not summarize, sample, or truncate.
Format:
  {
    "<location>": {
      "<sensor>": {
        "sensorType": "...",
        "failureCount": N,
        "ticks": [{tickId, timestamp, grpcIp, error}]
      }
    }
  }

For locations with AUTO_MATERIALIZE sensor failures, also fetch
get_location_load_history(limit=5) and include deploy timestamps in the
output. (STANDARD sensor failures are almost always data-definition bugs,
not deploy-correlated — skip load history for those.) Note: load history
returns N most recent deploys regardless of timestamp — filter to in-window
deploys. Then fetch context ticks (ALL statuses) for each sensor with
failures:
  get_tick_history(same sensor, after_timestamp=<first_fail - 60>,
    before_timestamp=<last_fail + 60>, limit=50).
Per context tick: timestamp, status, gRPC IP if present. Flat array per
sensor.

Bucket failures by error-class fingerprint (first line of error.message)
in Phase 2 analysis — 61 identical `DagsterUnknownPartitionError` ticks on
one sensor is one finding, not 61.

## 4. Freshness state changes

search_assets iterates all LOADED code locations; collect every asset whose
definition has a `freshnessPolicy` (non-null). Then fan-out IN PARALLEL:
  get_asset_health(asset_keys=[<batch of ≤250>]).

Per asset record: key, freshnessStatus (HEALTHY/WARNING/DEGRADED/UNKNOWN),
freshnessStatusChangedTimestamp, latestMaterializationTimestamp,
freshnessStatusMetadata.lastMaterializedTimestamp.

Flag any asset whose `freshnessStatusChangedTimestamp` falls within
{UTC_START}–{UTC_END} — every transition in the window is a day-2 signal
even if the asset is currently HEALTHY. Dagster+ freshness alerts do NOT
surface in step 10 GKE events or step 11 Cloud Monitoring alerts; this is
the only step that captures them.

For each flagged asset also fetch materialization cadence:
  get_asset_materializations(asset_key, limit=10).
Phase 2 uses the cadence + policy config (deadline_cron,
lower_bound_delta) to detect cron-vs-arrival-time misalignments (a policy
whose deadline_cron fires BEFORE the asset's typical materialization time
produces nightly false-positive FAIL→PASS flaps).

## 5. Location load failures (depends on 3)

Per non-LOADED location: get_location_load_history(location_name, limit=10).
Collect: locationName, loadStatus, triggerTimestamp, error.

## 6. Schedule tick failures (depends on 3)

Per RUNNING schedule from step 3 IN PARALLEL:
  get_tick_history(name="<schedule>", repository_location_name="<loc>",
    statuses=["FAILURE"], limit=20, after_timestamp={EPOCH}).
Collect: tickId, timestamp, location, schedule name, error (300 chars).

Only terminal failures matter here. The scheduler daemon retries gRPC calls
indefinitely within a single tick evaluation — agent-level "Error serving
request" logs during code server preemption are noise, not tick failures.
A tick that eventually succeeds after agent retries is not a failure.

Note: on Dagster+ Hybrid, the asset/sensor/schedule daemons run in the
Dagster Cloud control plane, not in the local agent. `max_tick_retries` in
the OSS `dagster.yaml` schema does NOT apply — the Dagster+ full deployment
settings reference (`concurrency`, `run_monitoring`, `run_retries`,
`sso_default_role`) exposes no tick-retry knob. Terminal
`DagsterUserCodeUnreachableError` ticks remain terminal; the only
mitigations are reducing the underlying cause (Service recreation rate or
preemption) — not retry.

If Phase 2 analysis needs to investigate schedule alert noise, query GCP agent
container logs: `textPayload:("Error serving request" AND "schedule" AND
"UNAVAILABLE")` on `user-cloud-dagster-cloud-agent-agent` pods.

## 7. Agent health

get_cloud_agents(errors_after={EPOCH}). Steady state matches the
`dagsterCloudAgent.replicas` setting in `.k8s/dagster/values-override.yaml`
(currently 1 — dropped from 2 to eliminate dual-agent Service recreation
churn). Extract per agent: id, status, lastHeartbeatTime, errors (timestamp
+ message, 300 chars). Discard codeServerStates/runWorkerStates. Include
agents with heartbeat in window + all RUNNING. Note: the errors array is
capped at 25 per agent — if 25 errors are returned, earlier errors in the
window were evicted.

## 8. Agent pod churn (depends on 7)

Skip ONLY IF every agent has status=RUNNING AND errors=[] (empty array).
If any agent has status != RUNNING OR a non-empty errors array, run this
step. Otherwise count pod creates (step 10 captures preemption events for
all pods):

mcp__gke__query_logs(project_id="teamster-332318",
  query='resource.type="k8s_cluster"
    AND log_name="projects/teamster-332318/logs/events"
    AND resource.labels.cluster_name="autopilot-cluster-dagster-hybrid-1"
    AND jsonPayload.involvedObject.namespace="dagster-cloud"
    AND jsonPayload.involvedObject.name:"user-cloud-dagster-cloud-agent-agent"
    AND jsonPayload.reason="SuccessfulCreate"',
  time_range={startTime: "{UTC_START}", endTime: "{UTC_END}"}, limit=100,
  format="{{.timestamp}} {{.jsonPayload.involvedObject.name}} {{.jsonPayload.message}}").
Normal Helm upgrade at replicas=1, maxSurge=200% = 2 creates per rollout. More
than 3 creates in a short window = crash loop or preemption storm.

## 9. Daemon health

get_daemon_health(). Collect: daemonType, healthy. Only include errors if
unhealthy. Skip lastHeartbeatTime (null on Cloud).

## 10. GKE critical events

Two queries IN PARALLEL. CRITICAL: include `format=` on query_logs and the
`jsonPayload.reason=(...)` clause on both — without either, the tools return
full JSON per log entry (hundreds of bytes each) and WILL exceed the
tool-result token limit. If the subagent hits "response exceeds token limit",
it means the query or format was malformed — retry with the exact template
below, NOT a smaller time window.

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
  time_range={start_time: "{UTC_START}", end_time: "{UTC_END}"}, limit=100,
  format="{{.timestamp}}|{{.resource.labels.pod_name}}|{{.jsonPayload.reason}}|{{.jsonPayload.message}}").

The `format=` parameter is MANDATORY. Omitting it makes query_logs return the
full JSON representation of each entry (resource labels, operation, insertId,
receiveTimestamp, etc.) — even 1 matching event can be ~1KB, and 100 events
blow the tool-result token limit. The pipe-delimited template above keeps each
event under ~200 bytes.

Note: `mcp__gke__query_logs` uses snake_case `time_range` keys
(`start_time`/`end_time`), NOT camelCase. camelCase is silently accepted but
ignored, yielding an unbounded query.

Per entry: timestamp, reason, pod/object name, message. Verify all entries
have timestamps within {UTC_START}–{UTC_END} before writing — discard any
outside the window.

Both tools cap at 100 results. Paginate per contract; cursor is
`time_range.start_time = <last_returned + 1s>` (results ascending).
Deduplicate by timestamp + pod name across pages.

If a response still exceeds token limits AFTER confirming format= and
reason-filter are correct, split by reason: run one query per reason value
and concatenate results. Do NOT skip the step or write empty results with a
"deferred" note — the Phase 2 correlation depends on real pod events.

## 11. Alerts

Two calls IN PARALLEL:
  list_alerts(parent="projects/teamster-332318", filter='state="OPEN"').
  list_alerts(parent="projects/teamster-332318",
    filter='open_time >= "{UTC_START}"', orderBy="open_time desc", pageSize=50).
Deduplicate. Per alert: name, displayName, state, open_time, close_time,
resource labels, metric type, policy. Pod type from name:
  dagster-step-* → step worker, dagster-run-* → run coordinator,
  <loc>-prod-* → code server.

## 12. Error groups

mcp__observability__list_group_stats(projectName="projects/teamster-332318",
  timeRangePeriod="PERIOD_30_DAYS", order="LAST_SEEN_DESC", pageSize=25).
Paginate per contract via pageToken.

Capture ALL groups with resolutionStatus="OPEN" regardless of when they were
last seen — open groups are actionable cleanup targets whether or not they
triggered in the day-2 window. `timeRangePeriod` caps the retrieval window at
30 days; if the intent is a weekly cleanup pass, one month is wide enough.
Use `PERIOD_30_DAYS` (not narrower), because `PERIOD_1_DAY` silently omits
groups last-seen >24h ago even though they are still OPEN.

Bucket in post-processing (OPEN groups only — drop RESOLVED / MUTED from
both buckets):
  - inWindow: resolutionStatus="OPEN" AND lastSeenTime within window →
    Phase 2 correlates with runs/ticks for root-cause linkage
  - staleOpen: resolutionStatus="OPEN" AND lastSeenTime older than
    UTC_START → Phase 2 surfaces as cleanup / emerging-issue candidates
    without correlating to timeline
RESOLVED and MUTED groups are retained in the file for audit visibility
but get neither bucket flag (both booleans=false). Phase 2 ignores them
unless they transitioned to RESOLVED inside the window (separate cleanup
signal, not an incident).

Many OPEN groups are false positives from retry-wrapped helpers that log
`.exception()` at ERROR severity on transient failures the retry layer
recovers from (see teamster/CLAUDE.md — "Don't log.exception inside
retry-wrapped helpers"). Flag these patterns rather than treating them as
active incidents.

Per group: ID, count, firstSeenTime, lastSeenTime, exception (300 chars),
services, resolutionStatus.

## 13. OOM drill-down (depends on 1)

Skip if no "Node OOM/eviction" runs. Per OOM run:
list_time_series(name="projects/teamster-332318",
  filter='metric.type="kubernetes.io/container/memory/used_bytes"
    AND resource.labels.pod_name=starts_with("<prefix>")',
  interval={startTime: "<run_start-5m>", endTime: "<run_end+5m>"},
  aggregation={alignmentPeriod: "60s", perSeriesAligner: "ALIGN_MAX"}).
Pod prefix: <loc>-prod-* (code server), dagster-run-* (coordinator),
dagster-step-* (step). Collect: peak bytes, limit bytes.

## 14. Queued/stuck runs

list_runs(statuses=["QUEUED","NOT_STARTED","MANAGED","STARTING"],
  created_after={EPOCH}, limit=20).
Flag runs queued >15 min. Collect: runId, jobName, status, startTime, duration.

## 15. Backfills

IN PARALLEL: list_backfills(status="REQUESTED", limit=10),
list_backfills(status="FAILED", created_after={EPOCH}, limit=10).
Collect: backfillId, status, numPartitions, timestamp, error.

Write JSON to .claude/scratch/day2/:
  step-01-failed-runs.json, step-02-retries.json, step-03-ticks.json,
  step-04-freshness.json, step-05-load-failures.json,
  step-06-schedule-ticks.json, step-07-agents.json,
  step-08-agent-pod-churn.json, step-09-daemons.json,
  step-10-gke-events.json, step-11-alerts.json,
  step-12-error-groups.json, step-13-oom-metrics.json,
  step-14-queued-runs.json, step-15-backfills.json.
Skip empty steps.

## Subagent partial-return fallback

If the Phase 1 subagent returns with some steps missing from the manifest
(context budget exhaustion, timeout, or errored tool call), do NOT
re-dispatch the full Phase 1. Identify which step files are missing or
empty and dispatch a follow-up haiku subagent scoped to only those steps,
passing the same {EPOCH}/{UTC_START}/{UTC_END} and the pagination
contract. Merge the new files into the same scratch directory before
Phase 2.

## Validation (after all writes)

Re-read each JSON file and verify:
  (a) Pagination terminated: every file's `pagination.complete` MUST be
      STRICTLY lastPageSize < limit. If lastPageSize == limit, complete is
      FALSE regardless of what was written — re-paginate. If any file has
      complete=false, you stopped paginating early — go re-query that step
      until a short page is returned. This check is the PRIMARY guard
      against silent truncation. Do NOT skip it. Comparing two numbers from
      the same truncated query is not a check — it passes vacuously by
      construction.
  (b) Step 1: successCount + failureCount + canceledCount > 0 (at least one
      status must have runs — 0/0/0 means pagination failed; re-query).
  (c) Step 2: every retry entry has retryStatus ∈ {SUCCESS, FAILURE}. Any
      "UNKNOWN", null, or missing value is a bug — re-fetch get_run_logs
      for that runId and derive from the terminal event.
  (d) Step 3: per-location tick array length == failureCount AND
      pagination.complete=true. If either fails, re-query and rewrite.
  (e) Step 10: all timestamps fall within {UTC_START}–{UTC_END}. Remove any
      out-of-window entries. ALSO: for every Evicted/OOMKilling pod event
      with a pod name matching `dagster-run-<runId>-*`, look up that runId
      in step 1's SUCCESS count context OR list_runs(run_ids=[<id>]). If
      the run's status is SUCCESS AND the pod event timestamp is within
      60s AFTER the run's endTime, tag the event with
      "post_success_cleanup": true. Phase 2 must exclude these from OOM
      findings — pod cleanup after a successful run is not a failure.
Fix any mismatches before returning.

Return JSON manifest: {filename: absolute_path}.
```

## Phase 2: Correlate and report

Read from `.claude/scratch/day2/` per manifest.

**Pagination gate (run BEFORE any analysis)**: For each per-step JSON, check
`pagination.complete`. If any file has `complete: false`, do NOT draw
conclusions from it — re-run the corresponding step's pagination loop yourself
(do not re-dispatch Phase 1) and overwrite the file. Counts and patterns from
truncated data are silently wrong; the rest of the analysis depends on them.

**Temporal overlap gate**: Before linking signals as cause/effect, verify
`max(start_A, start_B) < min(end_A, end_B)`. If false → independent findings.

**Reclassify** runs using cross-signal context:

| From                              | To                | Trigger signal                                                                                                 |
| --------------------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------- |
| Unclassified / Connection failure | Agent API timeout | Agent `errors` array contains `ReadTimeout` + `*.agent.dagster.cloud` in same window (not visible in GKE logs) |
| Code error                        | K8s API timeout   | Error class is actually `DagsterK8sUnrecoverableAPIError` — stack-trace match alone is insufficient            |
| Unclassified                      | Node OOM/eviction | GKE pod event `OOMKilling` or `Evicted` for run's pod — then run step 13 drill-down                            |

**Tick failure analysis**: For any location with >5 gRPC UNAVAILABLE tick
failures, run this procedure before attributing a root cause:

1. Sort failure ticks ascending, cluster by gap >120s.
2. Count distinct gRPC IPs across the failure ticks. **Multiple distinct
   ClusterIPs = agent-driven Service recreation.** The `dagster-cloud` agent's
   `unique_resource_name()`
   (`dagster_cloud/workspace/user_code_launcher/ utils.py`) uses a fresh
   `uuid4().hex[:6]` suffix on every reconcile, so every Deployment+Service
   recreate gets a new ClusterIP. Services are never updated in place — always
   delete-old / create-new. This IS a major source of tick gaps independent of
   preemption. Check the audit log
   (`protoPayload.methodName="io.k8s.core.v1.services.create"` on
   `dagster-cloud` namespace) to confirm and count recreations.
3. Cross-reference deploy timestamps from location load history (step 3 data)
   AND control-plane-driven reconciliations (any `update_timestamp` change
   triggers Service recreate — code pushes, workspace refreshes, UI
   interactions). Clusters aligned with a deploy/reconcile = Service recreation
   (1-3 ticks per recreate, bounded by code server startup p95 ~22s).
4. For remaining clusters: query GKE pod events for `<location>-prod-*` pods in
   the failure window (`mcp__gke__query_logs`, reason includes Preempted,
   Evicted, OOMKilling, Killing).
5. Classify by GKE event type:
   - **Preempted** "by pod \<uuid\>": priority preemption by run/step pods. In
     this codebase, code server pods run at priority 0 and run/step pods run at
     priority 1000 (`dagster-run` PriorityClass in
     `.k8s/dagster/values-override.yaml`) BY DESIGN — preempting code servers to
     free capacity for runs is intentional. Routine preemption is expected, not
     an escalation. Only escalate if: (a) preemption rate is
     sustained >>1/location/hour, (b) no correlation with run/step pod
     scheduling, or (c) code server pods are being preempted while run/step pods
     are idle. Check for hourly pattern (>50% in first 5 min of hour =
     schedule-triggered bursts). PDB is bypassed for priority preemption.
   - **Evicted** "low on resource: memory": node memory pressure. Monitor.
   - **OOMKilling**: container OOM (pod survives, container restarts).
     Investigate memory requests.
   - **Killing** without Preempted/Evicted: agent cleanup or deploy rollover.

Note: if no GKE pod events correlate with tick failures AND only a single gRPC
IP appears, consider health check starvation — long sensor evals blocking gRPC
threads. Diagnose: agent logs "failed a health check … 300 seconds" +
SuccessfulCreate frequency.

Rule of thumb: count Service recreations vs. pod preemptions in the window. If
recreations >> preemptions, Service churn is the dominant cause and no amount of
preemption mitigation (anti-affinity, priority tuning) will help — the fix is
agent-side (reducing reconciliation rate or upstream deterministic naming).

**Agent topology**: Steady state matches the `dagsterCloudAgent.replicas`
setting (currently 1 in `.k8s/dagster/values-override.yaml`). Flag deviations.
Cross-reference step 10 pod events filtered to
`user-cloud-dagster-cloud-agent-agent` for cause (Preempted/Evicted/OOMKilling).
Step 8 churn: at replicas=1 with maxSurge=200%, normal Helm upgrade = 2 creates.
3-4 creates = a rollout retry; >>4 = sustained storm.

In this codebase, agent pods run at priority 1000 (`dagster-agent`
PriorityClass) — same tier as run/step pods, so they CANNOT be preempted by
them. If you see "no agents have recently heartbeated" AND the agent pod shows
Preempted events, the preemption would have to come from a pod at priority >1000
(system-cluster-critical, etc.) — which is rare and worth investigating. If
agents are RUNNING with heartbeats but there's agent-level ReadTimeout to
`*.agent.dagster.cloud`, that's a control-plane connectivity issue, not
pod-level preemption.

**Timeline table** (ET): run failures, tick failures, terminal schedule tick
failures, location load failures, agent errors, code server failures, unhealthy
daemons, GKE events, alerts, error groups. Do not include schedule ticks that
succeeded after agent retries — those are noise from code server preemption.

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
- **Schedule tick failures:** ... (terminal only; omit if none)
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
if none. For step 12, split the Emerging Issues section into two subsections:

- **In-window groups** (step 12 `inWindow`): groups that surfaced during the
  day-2 window. **First, dedupe against the timeline:** each group's
  `affectedServices[].version` is a pod name (e.g.
  `dagster-step-<hash>-<suffix>` or `dagster-run-<runId>-<suffix>`). Query GCP
  logs for ERROR-severity entries on that pod within the group's lastSeenTime
  window and extract the `k8s-pod/dagster/run-id` label. If that runId is a
  failed run already listed in the timeline (step 1), mark the group "same event
  as run X" and fold it INTO the existing timeline entry instead of reporting it
  as a separate finding. Only groups with NO matching run are standalone
  emerging issues. For remaining (non-deduped) groups: if the stack trace
  matches a retry-recovered run, it is likely a false-positive from a
  retry-wrapped helper (see teamster/CLAUDE.md). Recommend changing the helper's
  log level in that case.
- **Stale open groups** (step 12 `staleOpen`): OPEN groups last-seen before the
  window. Treat as cleanup candidates. Note the last-seen date and whether the
  stack matches a retry-wrapped helper. These do not belong in the timeline.

When attributing an error group to a file, identify what is logging at ERROR
severity — GCP Error Reporting fires on ERROR logs, not on stack frames. A
traceback that passes through a file does NOT mean that file is the emitter.
`SIGTERM` during run preemption unwinds the stack through wherever execution was
when the signal arrived, so the top frames of the traceback will name whatever
helper was in-flight. Before proposing a fix to a file, confirm the file itself
emits ERROR-level logs for this path (read the source — not just that it appears
in the stack). Retry-wrapped helpers in `teamster/CLAUDE.md` log at WARNING and
do NOT file groups; stack frames through them are incidental.

**Actions**: No action (transient + retry success), Monitor
(recurring/emerging), Investigate (retry failure), Escalate (sustained platform
issue).

**Known self-resolving alerts**: kipptaf `dagster-step-*` CPU alerts (1000m
during import) self-resolve ~60s. Action: No action.

Flag truncation if any query hit pagination limits.

Reference `.k8s/CLAUDE.md` for scheduling, topology, security, config.

Write report to `.claude/scratch/day2/report.md`.

## Appendix: Targeted investigations (skip full skill)

### Specific agent ID query (not general health)

1. `get_cloud_agents(agent_id="<id>", errors_after=<epoch>)`
2. `list_runs(statuses=["FAILURE"])` ±30 min around error
3. GKE events same window

Run all three before concluding — even if agent looks healthy now.

### Re-execution chains

`get_run_group(run_id)` returns the full chain in one call. Don't traverse
parentRunId/rootRunId via get_run/list_runs.
