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

Run [`scripts/day2_collect.py`](scripts/day2_collect.py) — it issues all 15
queries (Dagster GraphQL + GCP REST + `gcloud logging`) and writes a single
artifact to `.claude/scratch/day2.json`. No subagent dispatch.

```bash
uv run .claude/skills/dagster-day2/scripts/day2_collect.py              # default: 5 PM ET prev biz day → now
uv run .claude/skills/dagster-day2/scripts/day2_collect.py --hours 24   # last N hours
uv run .claude/skills/dagster-day2/scripts/day2_collect.py --since 2026-03-29   # 5 PM ET that date → now
```

Output shape:

```json
{
  "window": {"epoch": ..., "utc_start": "...Z", "utc_end": "...Z"},
  "step_01_failed_runs": {"failureCount": N, "failures": [...], "successCount": N, "canceledCount": N, "successRunIds": [...]},
  "step_02_retries":     {"retries": [{"parentRunId":..., "retryRunId":..., "retryStatus":"SUCCESS|FAILURE"}]},
  "step_03_sensor_ticks":{"<location>": {"<sensor>": {"failureCount": N, "ticks": [{"tickId": "<str>", "timestamp": <float-seconds>, "error": "<str>", "errorChainTop": "<str>"}]}}},
  "step_04_freshness":   {"flaggedAssets": [...], "policyCount": N},
  "step_05_load_failures":{"loadFailures": [...]},
  "step_06_schedule_ticks":{"scheduleTickFailures": {"<loc>/<schedule>": [...]}},
  "step_07_agents":      {"agents": [...], "agentCount": N},
  "step_08_agent_pod_churn": {"events": [...], "skipped": bool},
  "step_09_daemons":     {"daemons": [...], "allHealthy": bool},
  "step_10_gke_events":  {"clusterEvents": [...], "podEvents": [{"timestamp":..., "podName":..., "reason":..., "message":..., "runId": "<uuid|null>", "runStatus": "SUCCESS|FAILURE|UNKNOWN"}]},
  "step_11_alerts":      {"alerts": [...]},
  "step_12_error_groups":{"groups": [{"groupId":..., "exception":..., "affectedServices":[{"service":...,"version":"<pod>"}], "exceptionLine":"<bottom-of-traceback or null>", "correlatedPodEvent":{"reason":"Preempted|Evicted|OOMKilling", "timestamp":..., "podName":...} | null, "category":"sigterm_during_import|preemption_artifact|unclassified"}], "buckets": {"inWindow":[], "staleOpen":[]}},
  "step_13_oom_metrics": {"oomRuns": [...], "skipped": bool},
  "step_14_queued_runs": {"runs": [...], "stuckCount": N},
  "step_15_backfills":   {"requested": [...], "failed": [...]},
  "step_16_asset_checks":{"totalChecks": N, "failedCount": N, "inWindow_error": [...], "inWindow_warn": [...], "stale_error": [...], "stale_warn": [...]},
  "step_17_degraded_assets":{"totalAssets": N, "degradedCount": N, "degraded": [{"asset":..., "latestRunId":..., "latestRunEndTime":...}], "byRun": [{"runId":..., "endTime":..., "count":N, "assets":[...]}]}
}
```

Each step 16 entry:
`{asset, check, status: "FAILED"|"EXECUTION_FAILED", severity: "ERROR"|"WARN"|"UNKNOWN", timestamp, runId, description, metadata}`.
WARN-severity FAILED checks include the `avro_schema_valid` checks that warn on
vendor schema drift; their `metadata` field carries the comma-separated `extras`
list. EXECUTION_FAILED checks have no evaluation (the check itself crashed) and
are bucketed alongside ERRORs because they need human triage.

Step 17 (`degraded assets`) uses `latestRun.status == "FAILURE"`. **Caveat: dbt
run failures are run-level, not step-level** — an asset whose own
materialization step succeeded mid-run can still be flagged here because the
overall run failed. Use the `byRun` grouping to identify the actual failing run,
then cross-reference `step_01_failed_runs.failures` for the run-level root
cause. Step-level recovery (e.g. auto-mat retry within minutes) leaves the prior
run's overall status as FAILURE, so a "degraded" asset whose last-mat timestamp
is later than its `latestRunEndTime` was actually recovered — read both fields.

Per-step error: if a step fails, its key holds `{"error": "..."}` instead of the
normal payload. Other steps still complete. Re-run the script if a key finding
depends on a failed step.

Run classification (`step_01_failed_runs.failures[].category`) is one of:
`Preemption/Interrupt`, `Node OOM/eviction`, `Scheduling failure`,
`K8s API failure`, `Backoff limit`, `Step preempt-hang`, `Network/SSH`,
`Connection failure`, `Code error`, `Infra timeout`, `Unclassified`. Phase 2 may
reclassify based on cross-signal context — see the reclassify table below.

## Phase 2: Correlate and report

**Required: Run the `superpowers:systematic-debugging` skill before drawing
conclusions.** Phase 1 surfaces signals; Phase 2 must reach root cause, not stop
at symptoms. For every distinct failure cluster you propose in the report:

1. **Root-cause investigation** — read errors completely, trace data flow
   backward to the source, verify against current code/data (issue bodies and
   prior session findings drift). State the hypothesis explicitly and test the
   smallest possible reproduction before writing it up.
2. **Pattern analysis** — find working examples in the same codebase; list every
   difference, however small. "Same shape as last week" without verification is
   rationalizing.
3. **Hypothesis & evidence** — name what you believe, name the evidence, call
   out what you can't verify. If the evidence chain has a gap, say so instead of
   papering over it.
4. **Tooling caveats first-class** — the collector's queries are proxies, not
   ground truth. Verify before reporting:
   - Step 17 `latestRun.status` is RUN-level, not step-level (caveat above).
   - Step 16 reflects the CURRENT workspace's checks; renamed/removed checks
     stop appearing (their prior FAILED state is no longer the truth).
   - Step 04 freshness flags policy presence, not violation state.

After investigation, run
[`scripts/day2_summarize.py`](scripts/day2_summarize.py) with `--details` to
print per-step counts, the error gate, and the failure / retry / GKE event /
error-group / asset-check / degraded-asset dump in one call. Drop `--details`
for the gate alone; fall back to reading `.claude/scratch/day2.json` directly
for fields the dump omits.

```bash
uv run .claude/skills/dagster-day2/scripts/day2_summarize.py --details   # gate + details
uv run .claude/skills/dagster-day2/scripts/day2_summarize.py             # gate only
```

**Error gate**: The summarize script flags any `step_NN_*` key with an `"error"`
field and exits non-zero. If any step the analysis depends on errored, re-run
the collector (`uv run .claude/skills/dagster-day2/scripts/day2_collect.py`)
before drawing conclusions — partial data produces wrong findings.

**Temporal overlap gate**: Before linking signals as cause/effect, verify
`max(start_A, start_B) < min(end_A, end_B)`. If false → independent findings.

**Reclassify** runs using cross-signal context:

| From                              | To                | Trigger signal                                                                                                                                                                                                                                                                                                                                                                                                        |
| --------------------------------- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unclassified / Connection failure | Agent API timeout | Agent `errors` array contains `ReadTimeout` + `*.agent.dagster.cloud` in same window (not visible in GKE logs)                                                                                                                                                                                                                                                                                                        |
| Code error                        | K8s API timeout   | Error class is actually `DagsterK8sUnrecoverableAPIError` — stack-trace match alone is insufficient                                                                                                                                                                                                                                                                                                                   |
| Unclassified                      | Node OOM/eviction | GKE pod event `OOMKilling` or `Evicted` for run's pod — then run step 13 drill-down                                                                                                                                                                                                                                                                                                                                   |
| Infra timeout                     | Step preempt-hang | `runFailureMessage: Exceeded maximum runtime` AND `engineEventMatch` contains `Exiting to prevent re-running`. Step pod was preempted, replacement bailed via `verify_step` exit-0, K8s Job marked `Complete` so `check_step_health` stays healthy and run hangs until `max_runtime`. Self-heals via `dagster/will_retry`. Upstream: dagster-io/dagster#33728. Do not chase as control-plane / PowerSchool / network. |

**Pod-event run attribution (`step_10_gke_events.podEvents`):** for any
`dagster-run-*` Evicted/Preempted event, the collector parses the runId from the
pod name and tags the event with `runId` + `runStatus`:

- `runStatus: "SUCCESS"` — run already terminated successfully. The evicted pod
  was a disrupted scheduling attempt absorbed by
  `podFailurePolicy: DisruptionTarget=Ignore`; the Job controller spawned a
  replacement that ran the work cleanly. **No impact, no action** — do not call
  it "orphan" or "stale Job"; the Job is/was active and behaved correctly.
- `runStatus: "FAILURE"` — runId is in `step_01_failed_runs.failures`. The
  eviction may be the proximate cause; cross-reference the failure's `category`
  and `errorClass`.
- `runStatus: "UNKNOWN"` — runId is outside the window, or the pod name didn't
  match the `dagster-run-<uuid>-` pattern (e.g. `<location>-prod-*` code servers
  — see Tick failure analysis step 5 for those).

To enumerate every pod attempt for a runId (useful when `runStatus: FAILURE` and
you need to confirm which attempt was terminal): audit log
`protoPayload.methodName="io.k8s.core.v1.pods.create" protoPayload.resourceName=~"core/v1/.../pods/dagster-run-<runId>-.*"`.
Dagster's `startTime` reflects execution start on the surviving pod — **not**
initial enqueue or first scheduling attempt. Do not use it to back-calculate
when K8s first tried to schedule.

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

{Omit only if BOTH `inWindow` and `staleOpen` are empty. Always list `staleOpen`
entries here — never in the timeline.}

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
only when BOTH `inWindow` and `staleOpen` are empty — a staleOpen entry alone is
still grounds to include the section. For step 12, split the Emerging Issues
section into two subsections:

- **In-window groups** (step 12 `inWindow`): groups that surfaced during the
  day-2 window. **First, check `category` + `correlatedPodEvent` (auto-resolved
  by the collector):**
  - `category: "sigterm_during_import"` with a `correlatedPodEvent` → the group
    is a SIGTERM-mid-import artifact of code-server preemption (the by-design
    priority-tier behavior in `.k8s/CLAUDE.md`). Do NOT include in Emerging
    Issues. Emit a single Actions row:
    `Mute | Error group <id> (SIGTERM during import, <count> hits)`. The
    traceback's deepest project-code frame names whichever module was importing
    when SIGTERM arrived (pathlib, pydantic, fldoe.schema, etc.) — that file is
    NOT the emitter; it was just in-flight when the signal arrived.
  - `category: "preemption_artifact"` → correlated to a preemption/eviction
    event but exception class is not a known SIGTERM type. Investigate
    `exceptionLine` before recommending action.
  - `category: "unclassified"` (no correlated pod event) → genuine emerging
    issue. Proceed with dedupe below.

  **Dedupe remaining (uncorrelated) groups against the timeline:** each group's
  `affectedServices[].version` is a pod name. Query GCP logs for ERROR-severity
  entries on that pod within the group's lastSeenTime window and extract the
  `k8s-pod/dagster/run-id` label. If that runId is a failed run already listed
  in the timeline (step 1), mark the group "same event as run X" and fold it
  INTO the existing timeline entry instead of reporting it as a separate
  finding. Only groups with NO matching run are standalone emerging issues. For
  remaining (non-deduped) groups: if the stack trace matches a retry-recovered
  run, it is likely a false-positive from a retry-wrapped helper (see
  teamster/CLAUDE.md). Recommend changing the helper's log level in that case.

  **Use `exceptionLine`, not `exception`, for triage.** The `exception` field is
  the 300-char truncated header that Error Reporting groups by — often just the
  entry-point line (`Traceback... sys.exit(main())`). The collector resolves the
  bottom-of-traceback class into `exceptionLine` via a pod-log query; that is
  the real exception class.

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

**Asset checks (step 16) integration**:

- **`inWindow_error`** entries → Timeline (and Impact if they correspond to a
  blocked run). These are blocking data-quality failures.
- **`inWindow_warn`** entries → Emerging Issues, grouped by check name. The
  `avro_schema_valid` checks belong here — surface the affected asset list and
  the `extras` metadata; recommend either schema update (real new fields) or
  allowlist (vendor positional fillers).
- **`stale_error` / `stale_warn`** entries → Emerging Issues, labeled stale with
  last-run timestamp. Treat the same way you'd treat a stale error group:
  cleanup candidate, not active incident.
- Always reconcile against `step_01_failed_runs`: an ERROR-severity check FAILED
  in-window is usually the same event as a failed run. Fold into the existing
  timeline entry rather than double-reporting.

**Degraded assets (step 17) integration**:

- Surface the **`byRun` aggregation**, not the flat `degraded` list — one
  failing run typically marks 5–15 downstream assets as degraded; reporting
  per-asset overcounts the incident.
- **Verify each cluster is real before listing it.** For each `byRun` entry,
  read the run's actual failures from `step_01` — the run-level FAILURE may be
  due to a single failing model while every other selected model in the same run
  materialized successfully. In that case the "degraded" assets except the
  genuinely-failed one are noise.
- Clusters with `endTime` older than the day-2 window are stale candidates; they
  belong in Emerging Issues, not Impact.

**Actions**: No action (transient + retry success), Monitor
(recurring/emerging), Investigate (retry failure), Escalate (sustained platform
issue).

**Known self-resolving alerts**: kipptaf `dagster-step-*` CPU alerts (1000m
during import) self-resolve ~60s. Action: No action.

Flag any step with an `"error"` field — those signals are missing from the
timeline.

Reference `.k8s/CLAUDE.md` for scheduling, topology, security, config.

Write report to `.claude/scratch/day2-report-<YYYY-MM-DD>.md`, where the date is
the window end (`window.utc_end` from `day2.json`) converted to ET.

**Verify epoch conversions before drawing conclusions.** Dagster
`creationTime`/`startTime`/`endTime` are float seconds. Sanity-check every
conversion against the window's `utc_start`/`utc_end` in `day2.json` before
writing narrative — a single-hour math error can flip a "stale orphan pod" into
a "first scheduling attempt" (or vice-versa) and rewrite the entire root-cause
story. If a GKE event's UTC timestamp looks far from the run's computed UTC,
recompute before continuing.

**Run-never-started timestamps**: When a run times out before starting
(`Run timed out due to taking longer than N seconds to start`), `startTime` and
`endTime` in step 1 are both the failure-recorded time, not enqueue time.
Approximate the K8s Job create time as `startTime - N` (typically 480s), or
query the audit log directly:
`protoPayload.methodName="io.k8s.batch.v1.jobs.create" protoPayload.resourceName=~"dagster-run-<runId>.*"`.

**Audit logs > pod events for >1h-old bursts**: `mcp__gke__query_logs` with
`protoPayload.serviceName="k8s.io"` retains Job/Pod create/delete history for
days; pod events from `mcp__gcp-observability__list_log_entries` drop after ~1h.
For any burst analysis older than the day-2 collector's events lookback, query
audit logs by runId, not events.

**Slow pod startup at top-of-hour fan-out**: At scheduling spikes (e.g. 04:00
UTC / 00:00 ET), K8s Jobs are created promptly but pods can take 4–7 min to emit
their first log line (image pull + autoscaler node provision). The
`run_monitoring.start_timeout_seconds` measures from enqueue, so
run-never-started failures during these windows are an autoscaler-latency
symptom — not an agent or K8s-API symptom.

## Appendix: Targeted investigations (skip full skill)

### Specific agent ID query (not general health)

1. `get_cloud_agents(agent_id="<id>", errors_after=<epoch>)`
2. `list_runs(statuses=["FAILURE"])` ±30 min around error
3. GKE events same window

Run all three before concluding — even if agent looks healthy now.

### Re-execution chains

`get_run_group(run_id)` returns the full chain in one call. Don't traverse
parentRunId/rootRunId via get_run/list_runs.
