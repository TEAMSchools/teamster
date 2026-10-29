---
name: dagster-day2
disable-model-invocation: true
description: >-
  Use when checking Dagster health after an overnight window, or when runs,
  sensor or schedule ticks, code locations, or agents failed overnight and need
  a root cause and an incident report.
---

# Day-2 Operations Check

## Phase 1: Collect data

Run [`scripts/day2_collect.py`](scripts/day2_collect.py) — it runs all 17 steps
(Dagster GraphQL with a 1Password-issued token, GCP REST with ADC) and writes a
single artifact to `.claude/scratch/day2.json`. No subagent dispatch.

```bash
uv run .claude/skills/dagster-day2/scripts/day2_collect.py              # default: 5 PM ET prev biz day → now
uv run .claude/skills/dagster-day2/scripts/day2_collect.py --hours 24   # last N hours
uv run .claude/skills/dagster-day2/scripts/day2_collect.py --since 2026-03-29   # 5 PM ET that date → now
```

Output shape:

```json
{
  "window": {"epoch": ..., "utc_start": "...Z", "utc_end": "...Z"},
  "step_01_failed_runs": {"failureCount": N, "failures": [{"runId":..., "startTime":..., "endTime":..., "startTimeEt":"...", "endTimeEt":"...", "category":..., ...}], "successCount": N, "canceledCount": N, "successRunIds": [...]},
  "step_02_retries":     {"retries": [{"parentRunId":..., "retryRunId":..., "retryStatus":"SUCCESS|FAILURE"}]},
  "step_03_sensor_ticks":{"<location>": {"<sensor>": {"failureCount": N, "ticks": [{"tickId": "<str>", "timestamp": <float-seconds>, "error": "<str>", "errorChainTop": "<str>"}]}}},
  "step_04_freshness":   {"flaggedAssets": [...], "policyCount": N},
  "step_05_load_failures":{"loadFailures": [...]},
  "step_06_schedule_ticks":{"scheduleTickFailures": {"<loc>/<schedule>": [...]}},
  "step_07_agents":      {"agents": [...], "agentCount": N},
  "step_08_agent_pod_churn": {"events": [...], "skipped": bool},
  "step_09_daemons":     {"daemons": [...], "allHealthy": bool},
  "step_10_gke_events":  {"clusterEvents": [...], "podEvents": [{"timestamp":..., "timestampEt":"...", "podName":..., "reason":..., "message":..., "runId": "<uuid|null>", "runStatus": "SUCCESS|FAILURE|UNKNOWN"}]},
  "step_11_alerts":      {"alerts": [...]},
  "step_12_error_groups":{"groups": [{"groupId":..., "exception":..., "affectedServices":[{"service":...,"version":"<pod>"}], "exceptionLine":"<bottom-of-traceback or null>", "correlatedPodEvent":{"reason":"Preempted|Evicted|OOMKilling", "timestamp":..., "podName":...} | null, "category":"sigterm_during_import|preemption_artifact|unclassified"}], "buckets": {"inWindow":[], "staleOpen":[]}},
  "step_13_oom_metrics": {"oomRuns": [...], "skipped": bool},
  "step_14_queued_runs": {"runs": [...], "stuckCount": N},
  "step_15_backfills":   {"requested": [...], "failed": [...]},
  "step_16_asset_checks":{"totalChecks": N, "failedCount": N, "inWindow_error": [...], "inWindow_warn": [...], "stale_error": [...], "stale_warn": [...]},
  "step_17_degraded_assets":{"totalAssets": N, "degradedCount": N, "inWindowCount": N, "staleCount": N, "degraded": [{"asset":..., "latestRunId":..., "latestRunEndTime":..., "materializationType":"view|table|...|null"}], "byRun": [{"runId":..., "endTime":..., "endTimeEt":"...", "inWindow": bool, "count":N, "byMaterializationType":{"view": N, "non-dbt": N}, "assets":[...]}]}
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
`materializationType` is the dbt materialization, null for non-dbt assets
(counted as `non-dbt` in `byMaterializationType`). A plain dbt view re-runs only
on a code change (a `union_relations` view also re-runs after a parent's code
change), so a view in a stale cluster stays flagged until someone materializes
it by hand, even when its view in BigQuery works.

Per-step error: if a step fails, its key holds `{"error": "..."}` instead of the
normal payload. Other steps still complete. Re-run the script if a key finding
depends on a failed step.

Run classification (`step_01_failed_runs.failures[].category`) is one of:
`Preemption/Interrupt`, `Node OOM/eviction`, `Scheduling failure`,
`K8s API failure`, `Backoff limit`, `Step preempt-hang`, `BigQuery transient`,
`Network/SSH`, `Connection failure`, `Infra timeout`, `K8s pre-start kill`,
`Code error`, `Unclassified`. Phase 2 may reclassify based on cross-signal
context; see _Reclassify_ in Phase 2.

- `BigQuery transient`: BigQuery failed the job itself (`internalError`,
  `backendError`). dbt never resubmits a failed job, since `job_retries` covers
  only the submit and poll API calls, so the Dagster run retry is the only
  recovery. Not a code bug, unless the auto-retry fails the same way: then treat
  it as a query or code issue.
- `K8s pre-start kill`: `Discovered failed Kubernetes job` with no
  `LogsCapturedEvent` for the failing step, so the pod died at the K8s layer
  (FailedScheduling exhaustion, eviction after Scheduled, image pull) before
  step code ran. Same root cause as `Step preempt-hang`, different surface;
  retry typically succeeds once Autopilot stabilizes. Confirm with audit log
  `io.k8s.batch.v1.jobs.create` plus pod events for `dagster-step-<hash>-.*`.
  The check matches step keys, not attempts: a step with a `RetryPolicy` whose
  first attempt captured logs and whose retry pod died before starting lands in
  `Code error`, so check the attempts on a retried step's `Code error`.

## Phase 2: Correlate and report

Work in this order:

1. Run the summary and pass its error gate (below).
2. Invoke `superpowers:systematic-debugging`. Phase 1 surfaces signals; Phase 2
   reaches root cause, not symptoms.
3. Reclassify runs with cross-signal context (below).
4. Correlate signals across steps, passing the temporal overlap gate.
5. Write the report in the format below.

[`scripts/day2_summarize.py`](scripts/day2_summarize.py) with `--details` prints
per-step counts, the error gate, and the failure / retry / GKE event /
error-group / asset-check / degraded-asset dump in one call. Drop `--details`
for the gate alone; read `.claude/scratch/day2.json` directly for fields the
dump omits.

```bash
uv run .claude/skills/dagster-day2/scripts/day2_summarize.py --details   # gate + details
uv run .claude/skills/dagster-day2/scripts/day2_summarize.py             # gate only
```

**Error gate**: the summarize script flags any `step_NN_*` key with an `"error"`
field and exits non-zero. If a step the analysis depends on errored, re-run the
collector before drawing conclusions; partial data produces wrong findings. Name
any step still errored in the report, since its signals are missing from the
timeline.

The collector's queries are proxies, not ground truth:

- Step 17 `latestRun.status` is run-level, not step-level (caveat in Phase 1).
- Step 16 reflects the current workspace's checks; renamed or removed checks
  stop appearing, so their prior FAILED state is no longer the truth.
- Step 04 freshness flags policy presence, not violation state.

**Temporal overlap gate**: Before linking signals as cause/effect, verify
`max(start_A, start_B) < min(end_A, end_B)`. If false → independent findings.

**Reclassify** runs using cross-signal context:

- **Unclassified / Connection failure → Agent API timeout**: the agent `errors`
  array has `ReadTimeout` to `*.agent.dagster.cloud` in the same window. Not
  visible in GKE logs.
- **Code error → K8s API timeout**: the error class is
  `DagsterK8sUnrecoverableAPIError`. A stack-trace match alone is not enough.
- **Unclassified → Node OOM/eviction**: a GKE pod event `OOMKilling` or
  `Evicted` for the run's pod. Then drill down with step 13.
- **Infra timeout → Step preempt-hang**: `errorDetail` contains
  `completed without a step result` and `engineEventMatch` contains
  `Exiting to prevent re-running`. The step pod was preempted, its replacement
  exited 0 through `verify_step`, and K8s marked the Job `Complete`; the
  executor fails the step `ZOMBIE_JOB_GRACE_SECONDS` later (an op with a
  `RetryPolicy` retries in-run). Self-heals via `dagster/will_retry`. Upstream:
  dagster-io/dagster#33755. Do not chase it as control-plane, PowerSchool, or
  network.
- **Unclassified / Infra timeout → Slow-query timeout (dbt)**:
  `runFailureMessage: Exceeded maximum runtime` without
  `Exiting to prevent re-running`, and the step materialized assets
  (`MaterializationEvent` or `LogsCapturedEvent` present), so the run did real
  work. One model ran long: diff `AssetMaterializationPlannedEvent` against
  `MaterializationEvent` to find it, then check that model's job in
  `JOBS_BY_PROJECT`. The same `total_bytes_processed` with several times the
  `total_slot_ms` across runs is a transient BigQuery straggler that self-heals
  on retry.

**`LogsCapturedEvent` presence is the K8s-vs-user-code discriminator.** The
collector applies it to health-check failures (`K8s pre-start kill`). For any
other step failure, before chasing user-code or PowerSchool/ADP/etc. theories,
page `mcp__dagster-plus__get_run_logs` for the run and look for a
`LOGS_CAPTURED` event naming the failing step. If none exists, the container
never started and the root cause is at the K8s layer. Step pod logs are not in
`k8s_container` logs; see `.claude/context/dagster.md` for where they are.

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
  — classify those via the GKE-event-type table in
  [references/tick-failure-analysis.md](references/tick-failure-analysis.md)).

To enumerate every pod attempt for a runId (useful when `runStatus: FAILURE` and
you need to confirm which attempt was terminal): audit log
`protoPayload.methodName="io.k8s.core.v1.pods.create" protoPayload.resourceName=~"core/v1/.../pods/dagster-run-<runId>-.*"`.
Dagster's `startTime` reflects execution start on the surviving pod — **not**
initial enqueue or first scheduling attempt. Do not use it to back-calculate
when K8s first tried to schedule.

**Tick failure analysis** (>5 gRPC UNAVAILABLE per location in the window): see
[references/tick-failure-analysis.md](references/tick-failure-analysis.md) for
the Service-recreation vs preemption disambiguation procedure. Don't attribute
root cause until you've worked through that procedure — Service churn and pod
preemption look identical from the tick log alone, but imply different fixes
(agent-side vs cluster-side).

**Agent topology**: Steady state matches `dagsterCloudAgent.replicas` in
`.k8s/dagster/values-override.yaml`. Flag deviations. Cross-reference step 10
pod events filtered to `user-cloud-dagster-cloud-agent-agent` for cause
(Preempted/Evicted/OOMKilling). Step 8 churn: at replicas=1 with maxSurge=200%,
normal Helm upgrade = 2 creates. 3-4 creates = a rollout retry; >>4 = sustained
storm.

In this codebase, agent pods run at priority 1000 (`dagster-agent`
PriorityClass) — above run/step and code server pods (0), so they CANNOT be
preempted by them. If you see "no agents have recently heartbeated" AND the
agent pod shows Preempted events, the preemption would have to come from a pod
at priority >1000 (system-cluster-critical, etc.) — which is rare and worth
investigating. If agents are RUNNING with heartbeats but there's agent-level
ReadTimeout to `*.agent.dagster.cloud`, that's a control-plane connectivity
issue, not pod-level preemption.

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

**Retry SUCCESS is not definitive for a dbt `table` model killed by
`max_runtime` mid-query.** dbt does not cancel the in-flight BigQuery job on run
termination (upstream limitation), so the orphaned job can complete minutes
later and `create or replace`-overwrite the successful retry's output with
staler data. Confirm the destination table's last write in `JOBS_BY_PROJECT`
post-dates the retry — not just that the retry succeeded. Mitigation lives in
the kipp\* dbt profiles (`job_execution_timeout_seconds`).

**Emerging issues**: Error groups not yet causing failures but increasing. Omit
the section only when BOTH `inWindow` and `staleOpen` are empty — a `staleOpen`
entry alone is still grounds to include it.

If any step 12 `inWindow` entries exist, read
[references/error-group-triage.md](references/error-group-triage.md) before
writing the section. Three categories (`sigterm_during_import`,
`preemption_artifact`, `unclassified`) need different treatment, including
auto-mute and timeline-dedupe rules. `staleOpen` entries are cleanup candidates
— list them with last-seen date.

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
- Verify each cluster against its run's `step_01` failures before listing it
  (the run-level caveat in Phase 1): only the genuinely failed model counts.
- `inWindow: false` clusters are stale candidates; they belong in Emerging
  Issues, not Impact.

**Actions**: No action (transient + retry success), Monitor
(recurring/emerging), Investigate (retry failure), Escalate (sustained platform
issue).

**Known self-resolving alerts**: kipptaf `dagster-step-*` CPU alerts (1000m
during import) self-resolve ~60s. Action: No action.

Reference `.k8s/CLAUDE.md` for scheduling, topology, security, config.

Write report to `.claude/scratch/day2-report-<YYYY-MM-DD>.md`, where the date is
the window end (`window.utc_end` from `day2.json`) converted to ET.

**Use the collector's `*Et` fields for times.** Any time you convert yourself
(Dagster epochs are float seconds; GKE timestamps are UTC), check against the
window's `utc_start`/`utc_end` first: a one-hour error can flip a stale orphan
pod into a first scheduling attempt and rewrite the root cause.

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

Single agent showing errors in the UI but no broader symptoms? The UI alone
isn't enough to conclude no impact — the agent may have already recovered, or
the impact may be visible only in run-side signals.

1. `get_cloud_agents(agent_id="<id>", errors_after=<epoch>)`
2. `list_runs(statuses=["FAILURE"])` ±30 min around error
3. GKE events same window

Run all three before concluding — even if agent looks healthy now.

### Re-execution chains

Walk the chain from run tags as `.claude/context/dagster-plus.md` describes
(`get_run` bullet, "the whole re-execution chain").
