---
name: dagster-day2
disable-model-invocation: true
description: >-
  Dagster platform health, run failures, GKE events, tick errors, overnight
  issues. Triggers: "what broke", "cluster healthy", "why did runs fail", "check
  production", or any production status question.
---

# Day-2 Operations Check

## Phase 1: Collect data

Run [`scripts/day2_collect.py`](../../../scripts/day2_collect.py) — it issues
all 15 queries (Dagster GraphQL + GCP REST + `gcloud logging`) and writes a
single artifact to `.claude/scratch/day2.json`. No subagent dispatch.

```bash
uv run scripts/day2_collect.py              # default: 5 PM ET prev biz day → now
uv run scripts/day2_collect.py --hours 24   # last N hours
uv run scripts/day2_collect.py --since 2026-03-29   # 5 PM ET that date → now
```

Output shape:

```json
{
  "window": {"epoch": ..., "utc_start": "...Z", "utc_end": "...Z"},
  "step_01_failed_runs": {"failureCount": N, "failures": [...], "successCount": N, "canceledCount": N},
  "step_02_retries":     {"retries": [{"parentRunId":..., "retryRunId":..., "retryStatus":"SUCCESS|FAILURE"}]},
  "step_03_sensor_ticks":{"<location>": {"<sensor>": {"failureCount": N, "ticks": [...]}}},
  "step_04_freshness":   {"flaggedAssets": [...], "policyCount": N},
  "step_05_load_failures":{"loadFailures": [...]},
  "step_06_schedule_ticks":{"scheduleTickFailures": {"<loc>/<schedule>": [...]}},
  "step_07_agents":      {"agents": [...], "agentCount": N},
  "step_08_agent_pod_churn": {"events": [...], "skipped": bool},
  "step_09_daemons":     {"daemons": [...], "allHealthy": bool},
  "step_10_gke_events":  {"clusterEvents": [...], "podEvents": [...]},
  "step_11_alerts":      {"alerts": [...]},
  "step_12_error_groups":{"groups": [...], "buckets": {"inWindow":[], "staleOpen":[]}},
  "step_13_oom_metrics": {"oomRuns": [...], "skipped": bool},
  "step_14_queued_runs": {"runs": [...], "stuckCount": N},
  "step_15_backfills":   {"requested": [...], "failed": [...]}
}
```

Per-step error: if a step fails, its key holds `{"error": "..."}` instead of the
normal payload. Other steps still complete. Re-run the script if a key finding
depends on a failed step.

Run classification (`step_01_failed_runs.failures[].category`) is one of:
`Preemption/Interrupt`, `Node OOM/eviction`, `Scheduling failure`,
`K8s API failure`, `Backoff limit`, `Step preempt-hang`, `Network/SSH`,
`Connection failure`, `Code error`, `Infra timeout`, `Unclassified`. Phase 2 may
reclassify based on cross-signal context — see the reclassify table below.

## Phase 2: Correlate and report

Read `.claude/scratch/day2.json`.

**Error gate**: For each `step_NN_*` key, check for an `"error"` field. If any
step the analysis depends on errored, re-run the collector
(`uv run scripts/day2_collect.py`) before drawing conclusions — partial data
produces wrong findings.

**Temporal overlap gate**: Before linking signals as cause/effect, verify
`max(start_A, start_B) < min(end_A, end_B)`. If false → independent findings.

**Reclassify** runs using cross-signal context:

| From                              | To                | Trigger signal                                                                                                                                                                                                                                                                                                                                                                                                        |
| --------------------------------- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unclassified / Connection failure | Agent API timeout | Agent `errors` array contains `ReadTimeout` + `*.agent.dagster.cloud` in same window (not visible in GKE logs)                                                                                                                                                                                                                                                                                                        |
| Code error                        | K8s API timeout   | Error class is actually `DagsterK8sUnrecoverableAPIError` — stack-trace match alone is insufficient                                                                                                                                                                                                                                                                                                                   |
| Unclassified                      | Node OOM/eviction | GKE pod event `OOMKilling` or `Evicted` for run's pod — then run step 13 drill-down                                                                                                                                                                                                                                                                                                                                   |
| Infra timeout                     | Step preempt-hang | `runFailureMessage: Exceeded maximum runtime` AND `engineEventMatch` contains `Exiting to prevent re-running`. Step pod was preempted, replacement bailed via `verify_step` exit-0, K8s Job marked `Complete` so `check_step_health` stays healthy and run hangs until `max_runtime`. Self-heals via `dagster/will_retry`. Upstream: dagster-io/dagster#33728. Do not chase as control-plane / PowerSchool / network. |

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

Flag any step with an `"error"` field — those signals are missing from the
timeline.

Reference `.k8s/CLAUDE.md` for scheduling, topology, security, config.

Write report to `.claude/scratch/day2-report.md`.

## Appendix: Targeted investigations (skip full skill)

### Specific agent ID query (not general health)

1. `get_cloud_agents(agent_id="<id>", errors_after=<epoch>)`
2. `list_runs(statuses=["FAILURE"])` ±30 min around error
3. GKE events same window

Run all three before concluding — even if agent looks healthy now.

### Re-execution chains

`get_run_group(run_id)` returns the full chain in one call. Don't traverse
parentRunId/rootRunId via get_run/list_runs.
