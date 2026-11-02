# Midnight preemption: design

Fixes [#6225](https://github.com/TEAMSchools/teamster/issues/6225).

## Intent

GKE Autopilot preempts our priority-0 run and step pods to admit
`gke-system-balloon-pod-*` pods on nodes it has just added ("Preempted in order
to admit critical pod"). Preemptions track node adds: about 0.04 per node when a
window adds 1–2 nodes, about 0.95 per node at 11 or more. Big launch bursts add
many nodes at once, so the midnight and 00:30 schedule fan-outs take most of the
damage.

From 10/21 17:00 to 11/02 13:29 ET, 190 of 321 failed runs failed by preemption
(`Preemption/Interrupt`, `Step preempt-hang`, `K8s pre-start kill`):

| Window      | Failed runs | Main jobs                                |
| ----------- | ----------- | ---------------------------------------- |
| 00:00–00:29 | 69          | DeansList 45, dbt automation 13, Forms 8 |
| 00:30–00:59 | 41          | ADP workers 39, dbt 2                    |
| 12:00–14:59 | 56          | 33 on 10/22 alone; DeansList midday 17   |

Most were retried and succeeded, but a failed run counts whether or not its
retry worked. 22 had no automatic retry left.

A second, related gap: the ADP freshness policy cannot see an incomplete ADP
sweep. `stg_adp_workforce_now__workers` rebuilds as soon as the first nightly
partition lands, so it is "fresh" mid-sweep, and the two roster tables are
"fresh" even if ADP never runs (they rebuild from other parents). IDAuto reads
the roster at 01:15 and could get a half-updated or stale roster with no alert.

Fixed means:

1. Failed runs caused by preemption drop sharply (metric below).
2. ADP and its downstream tables finish before 01:15 every night.
3. If the nightly ADP sweep is incomplete, staging does not build, the roster
   stays at yesterday's complete data, and an alert fires.

## Constraints (from the user)

- No cron moves, earlier or later.
- No revert of the `dagster-arm-first` ComputeClass (PR #6072).
- No shorter ADP window with a weekly full sweep.
- Step pods are negotiable; step parallelism is not.
- "Yesterday's roster is safer" than a partly updated one.
- The metric is failed runs, including runs whose retry succeeded.

## Non-goals

- Preemptions of pods whose run still succeeds (absorbed by
  `podFailurePolicy: DisruptionTarget=Ignore`). Fewer bursts will cut these too,
  but they are not the target.
- Incremental ADP pulls. `/hr/v2/workers` has no last-modified field or filter;
  ADP's change route is event notifications, a separate project.
- Moving Forms structure pulls into the responses sensor.

## Anti-goals

- Do not add `priorityClassName` to run, step or code-server pods.
  `tests/test_k8s_config.py::test_run_pods_and_code_servers_share_default_priority`
  stays as is.
- Do not add `build_last_update_freshness_checks` (superseded; see
  `src/teamster/core/CLAUDE.md`).
- Do not batch ADP partitions into one run. `UPathIOManager.handle_output`
  rejects multi-partition outputs, and one run per partition is what keeps the
  sweep parallel.

## Approaches

1. **Throttle with tag-concurrency caps.** A Dagster+ run-queue cap per job
   family (DeansList, ADP) spreads the burst. Cheap, but it lengthens every
   group, ADP slack before 01:15 shrinks to 3–13 minutes, and the cap is
   deployment-wide across districts.
2. **Fewer pods per run.** Drop step pods where they buy no parallelism. Cuts
   the burst by roughly half without slowing anything.
3. **Combined (chosen):** pre-provision nodes before midnight, cut pods per run,
   and gate ADP staging on a complete sweep. Caps stay in reserve.

Approach 3 attacks both causes: fewer nodes are needed (2), and the ones that
are needed exist before the burst (pre-provisioning), so balloon pods land on
nodes holding only placeholders.

## Design

Three phases, each its own PR, shipped in order. Measure after each.

### Phase 1: pre-provisioning

Placeholder pods hold nodes warm before the bursts. Our pods preempt them when
they need room, so Autopilot adds nodes (and admits balloon pods) before the
burst, not during it. Ship it as a normal change; if it does not cut midnight
preemptions, revert this phase alone.

Evidence that warm nodes are safe, 10/22–11/02: of 576 critical-pod preemptions,
557 hit a node less than 5 minutes old, 371 of them before the node's first
metric sample. Of 324 nodes with a preemption, 313 had their first one at birth.
Only 5 preemptions hit a node 15 or more minutes old. A node added at 23:45 is
15 minutes old at midnight.

Nodes added per night (EDT nights, 10/22–10/31): 24–35 from 00:00 to 00:15, 6–10
from 00:30 to 00:45, 0–5 from 23:30 to 23:59.

- A `PriorityClass` `dagster-placeholder`, value `-10`,
  `preemptionPolicy: Never`, `globalDefault: false`, in `extraManifests` of
  `.k8s/dagster/values-override.yaml`. Do not go below `-10`: one unverified
  report says Autopilot skips scale-up for lower priorities.
- Two `CronJob`s in the same block, namespace `dagster-cloud`, both
  `timeZone: America/New_York`: `45 23 * * *` for the midnight burst and
  `15 0 * * *` for the 00:30 burst. Placeholders preempted at midnight are not
  replaced, and midnight's nodes may scale down before 00:30, so the 00:30 burst
  gets its own. Each:
  - Creates an Indexed `Job` with `parallelism` and `completions` of N,
    `backoffLimitPerIndex: 0`, and a `podFailurePolicy` rule
    `DisruptionTarget → FailIndex`. A preempted placeholder is not replaced; a
    replacement would go Pending and pull a new node mid-burst, which is the
    thing we are avoiding.
  - `activeDeadlineSeconds: 5400` (through 01:15), so it cleans up without a
    scaler or RBAC.
  - Pod: `priorityClassName: dagster-placeholder`, a pause container, requests
    equal to one run pod (500m CPU, 2 GiB, from `runK8sConfig`), the
    `cloud.google.com/compute-class: dagster-arm-first` nodeSelector and the
    arm64 toleration run pods use. No `safe-to-evict: "false"` annotation.
- A test in `tests/test_k8s_config.py` asserting the placeholder priority is
  below 0 and its pod selects the `dagster-arm-first` class.
- Deploy is the manual `helm upgrade` in `.k8s/CLAUDE.md`; the user runs it.

Risks to watch the first nights: active migration moving placeholders, and
Autopilot scaling idle placeholder nodes down before the burst. Either would
show as node adds at 00:00 despite the placeholders.

Billing: placeholders bill per pod, N × (500m, 2 GiB) × 90 minutes nightly.

### Phase 2: fewer pods per run

Single-step runs (one asset per run) gain nothing from a step pod. Run them
in-process in the run pod.

| Job                                    | Assets per run | Executor                |
| -------------------------------------- | -------------- | ----------------------- |
| ADP workers (`kipptaf`)                | 1              | in-process              |
| Forms `form` schedule (`kipptaf`)      | 1              | in-process              |
| DeansList month and midday (districts) | 1              | in-process              |
| DeansList static (5) and year (2)      | 2–5            | `multiprocess_executor` |

- Set the executor on these jobs only (`define_asset_job(executor_def=...)` or
  the equivalent where each schedule builds its job). Code locations keep
  `zombie_aware_k8s_job_executor` as the default for everything else.
- Each ADP partition stays its own run, so the sweep stays parallel across run
  pods. Multiprocess keeps the static and year steps parallel inside one pod.
- Run and step pods share `runK8sConfig` (500m / 2 GiB requests, 1750m / 2.5 GiB
  limits). In-process runs do the same work a step pod did, so the same size
  fits. Multiprocess runs hold up to 5 steps at once: measure peak memory on a
  branch deployment and, if needed, raise it with a `dagster-k8s/config` tag on
  those jobs (`resources` is an allowed field under
  `onlyAllowUserDefinedK8sConfigFields`).
- No recovery is lost. Today a run pod lost mid-run fails the run ("Execution
  was interrupted unexpectedly"; 96 of the 141 matched preemption failures), so
  run resume is not saving runs. Runs that lost a run pod and still succeeded
  lost it before starting, and Kubernetes started a replacement (4 of 4
  sampled); that path is unchanged in-process. Run retries cover the rest as
  today.

Forms: pull only edited forms. A new response does not change a form's Drive
`modifiedTime`; only edits do. The `form` schedule:

- gains the `google_drive` resource;
- calls `GoogleDriveResource.get_modified_times()` on the dynamic partition keys
  (not the folder listing; some forms with responses now live in personal My
  Drives);
- yields a `RunRequest` only for forms modified in the last 25 hours.

Limit: a failed form run is not retried the next night unless the form is edited
again. Write that as a `shortcut:` comment.

Estimated pods: DeansList about 400 → 150, ADP 90 → 45, Forms 44 → 0–4.

### Phase 3: ADP staging waits for the complete sweep

`stg_adp_workforce_now__workers` builds once per night, after all partitions the
00:30 tick requested have materialized, and not before.

Two mechanisms fit; the builder picks one with the test below:

- **Schedule launches an asset backfill** covering tonight's 45 partitions plus
  staging. The backfill runs staging only after every parent partition succeeds,
  and skips it if any fails.
- **Custom automation condition** on staging that is true only when every
  partition in the schedule's window has updated since the `30 0 * * *` tick.

Either way, staging's current eager condition must stop firing on a single
partition. The only automatic trigger is "every partition in tonight's window
has landed since the tick", which a daytime rerun that fills the gap also
satisfies. A deploy that changes staging's code does not rebuild it
automatically; a person can still materialize it by hand.

Decision test (automation-condition style, ephemeral instance, per
`tests/CLAUDE.md`): with 44 of 45 window partitions materialized since the tick,
staging is not requested; with all 45, it is requested once.

Alerting and freshness, in `src/teamster/code_locations/kipptaf/freshness.py`:

- Keep `adp_wfn_policy` (deadline `15 1 * * *`, 45-minute lower bound) on
  `stg_adp_workforce_now__workers`. Once staging builds only on a complete
  sweep, this policy fails exactly when the sweep is incomplete or late.
- Remove it from `int_people__staff_roster` and
  `int_people__staff_roster_history`. They rebuild from other parents, so the
  policy passes there without ADP data and gives false comfort.
- Leave `stg_people__employee_numbers` as is.
- Confirm a Dagster+ alert policy routes freshness failures for staging to the
  data team. Add one if not.

Incomplete sweep, end to end: some partition fails its retries → staging not
built → roster stays at yesterday's complete data → IDAuto at 01:15 and
DeansList at 01:25 read yesterday → freshness alert at 01:15. When the missing
partition is rerun, staging builds and the roster catches up.

Timing: ADP landed 00:34–00:39 on 11/02 and the downstream chain took about 12
minutes, so staging at ~00:40 puts the roster around 00:52, inside 01:15.

### Reserve: tag-concurrency caps

Only if Phases 1–2 miss the target after two weeks. Before sizing an ADP cap,
read the `adp_wfn_api` pool limit and granularity (both ADP assets set
`pool="adp_wfn_api"`) from the same settings output: run tags plus
`tag_concurrency_limits` in Dagster+ deployment settings for DeansList (cap 2,
`dagster/priority` static > month > year) and ADP (cap 10). The user applies
them with `dagster-cloud deployment settings set-from-file`; the settings key
and existing limits are unconfirmed.

## Success metric

Target: zero preemption-caused failed runs (the three categories above) from
00:00 to 01:00 over the two weeks after Phase 2 ships. Any such failure in that
window after two weeks triggers the reserve caps. The midday window is reported
but not judged. Baseline: 10/21–11/02 excluding 10/22. Collect with the day-2
collector (`--since`). Also report pods started per 10 minutes from 00:00 to
01:00, and for Phase 3, nights when staging built after 01:15.

## Left to the builder

- N placeholder pods per CronJob: enough run-pod-sized pods to hold the node
  counts above (about 30 at midnight, about 10 at 00:30), from pods per node in
  the same metrics. Re-size after Phase 2 shrinks the burst.
- Which Phase 3 mechanism, settled by the decision test.
- Multiprocess pod sizing, from a branch-deployment measurement.
- Where each DeansList job's executor is set in `libraries/deanslist/`.
