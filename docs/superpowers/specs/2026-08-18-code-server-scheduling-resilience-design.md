# Code server scheduling resilience

Design for [#4907](https://github.com/TEAMSchools/teamster/issues/4907).

Date: 2026-08-18

## Problem

Code locations intermittently fail to load and stay failed until a human
intervenes. Separately, the Dagster+ hybrid agent logs
`DagsterUserCodeUnreachableError: Could not reach user code server` at roughly
100 occurrences per week.

Both come from the same place: a replacement code-server pod cannot be scheduled
quickly, and the agent abandons it while Kubernetes is still legitimately
working on placement.

### The terminal failure is the priority

A timed-out code-server deployment does **not** retry. Verified in
`dagster_cloud/workspace/user_code_launcher/user_code_launcher.py`:

```python
def _should_trigger_recovery(...) -> bool:
    if not isinstance(server_or_error, SerializableErrorInfo):
        return False  # local code server is healthy, no recovery needed
    if location_key in control_plane_error_locations:
        return False  # control plane agrees there is an error, don't retry
```

The recovery path fires only when the agent holds a local error while the
control plane believes the location is healthy. Once the timeout error is
uploaded, both agree, and recovery is suppressed. Normal reconciliation
redeploys only when
`actual_entry.update_timestamp != desired_entry.update_timestamp`, which changes
on a new deploy. The periodic health check needs a running endpoint, which a pod
that never started does not have.

So the location stays `ERROR` until someone pushes a commit or clicks redeploy.
There is no agent setting that changes this; the launcher exposes
`DAGSTER_CLOUD_DISABLE_LOCAL_ERROR_SERVER_RECOVERY`, which only turns recovery
off.

### Why placement is slow

A replacement code-server pod must satisfy four hard constraints at once:

1. `nodeSelector` of `cloud.google.com/compute-class: Scale-Out` plus
   `kubernetes.io/arch: arm64`, so only NAP-provisioned T2A nodes qualify
   (`.k8s/dagster/values-override.yaml`).
1. Its own per-location `requiredDuringSchedulingIgnoredDuringExecution`
   anti-affinity on `location_name` plus `kubernetes.io/hostname`, from each
   district's `dagster-cloud.yaml`.
1. Symmetric enforcement of the run pods' `required` anti-affinity against
   code-server labels. Kubernetes evaluates existing pods' anti-affinity when
   placing a new pod, which produces the
   `didn't satisfy existing pods anti-affinity rules` line. A code server
   therefore cannot land on any node hosting a run or step pod.
1. Whatever cpu and memory remains after the above.

During busy periods nearly every arm64 node hosts run pods, so the eligible set
reaches zero and NAP must build a new node. Captured from kipptaf at
approximately 2026-08-18 14:30 UTC:

```text
Exception: Timed out waiting for deployment kipptaf-prod-5c5421.

Pod status: Pending

No logs for container 'dagster'.

FailedScheduling: 0/7 nodes are available: 1 node(s) didn't match Pod's node
affinity/selector, 1 node(s) didn't match pod anti-affinity rules, 2 node(s)
had untolerated taint(s), 3 Insufficient cpu, 3 Insufficient memory.
```

### The governing timeout was never tuned

Two timeouts govern code-server startup and the failing path uses the one still
at its default:

| Helm key                                | Governs                                                 | Current        |
| --------------------------------------- | ------------------------------------------------------- | -------------- |
| `workspace.deploymentStartupTimeout`    | creating the Deployment, i.e. getting the pod scheduled | unset, so 300s |
| `workspace.serverProcessStartupTimeout` | waiting for readiness once the Deployment exists        | 300            |

`.k8s/CLAUDE.md` documents NAP `FailedScheduling` waits of 3 to 9 minutes. A 300
second deadline sits inside that range, so failures are expected whenever
provisioning lands in the upper half of normal.

## Constraints

- **The run-pod-to-code-server isolation stays hard.** It was added in response
  to a real incident in which run pods starved and killed code servers. Relaxing
  `required` to `preferred` there is out of scope.
- **Code-server priority stays at 0.** Promoting code servers above
  `dagster-run` would make run pods wait instead, reversing a deliberate
  decision recorded in `.k8s/CLAUDE.md`. Explicitly declined.
- Helm value changes require a manual `helm upgrade`; they do not ship with a
  git push.

## Measured baseline

Cloud Logging, code-server pods only (`involvedObject.name` containing `-prod-`)
in the `dagster-cloud` namespace. Retention is 30 days, so nothing before
2026-07-19 is observable.

| Week         | Agent gRPC errors | Killing | ScaleDown | Preempted | Evicted | FailedScheduling |
| ------------ | ----------------- | ------- | --------- | --------- | ------- | ---------------- |
| Jul 20-27    | 85                | 122     | 42        | 21        | 0       | 472              |
| Jul 28-Aug 4 | 134               | 197     | 59        | 37        | 0       | 454              |
| Aug 4-11     | 106               | 118     | 48        | 22        | 0       | 213              |
| Aug 11-18    | 100               | 142     | 38        | 32        | 0       | 438              |

The reported recent uptick is not present; the peak was Jul 28 to Aug 4 and the
two most recent weeks are lower. This is chronic, not a regression.

`Evicted` at 0 across all four weeks confirms the isolation is doing its job. It
buys that at the cost of the preemptions and scheduling failures.

## Design

Three phases, separately landable, ordered so value arrives before risk. Each
phase is independently revertable.

### Phase 1: no-tradeoff tuning

| Change                                                        | Location                                              | Effect                                                               |
| ------------------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------- |
| `deploymentStartupTimeout: 900`                               | Helm `workspace`                                      | agent waits out a normal NAP provision instead of abandoning at 300s |
| add `cluster-autoscaler.kubernetes.io/safe-to-evict: "false"` | `serverK8sConfig.podTemplateSpecMetadata.annotations` | removes 38 to 59 autoscaler relocations per week                     |
| self-anti-affinity `required` to `preferred`                  | all five `dagster-cloud.yaml`                         | lets a rollover reuse the outgoing pod's node                        |

The self-anti-affinity change is the highest-leverage item and needs
justification, because it looks like a safety feature.

Each location's code server carries `required` anti-affinity against its **own**
`location_name` on hostname. With one replica per location it spreads nothing.
Its only live effect is forbidding the replacement pod from the outgoing pod's
node during a rollover — and that node is the single best candidate available:
it already has arm64 Scale-Out capacity sized for a code server, and the run-pod
anti-affinity guarantees no run pods are on it. The constraint specifically
excludes the one node guaranteed to satisfy every other requirement, forcing a
new node on every redeploy.

Cross-location spreading is handled separately by `topologySpreadConstraints`
(`ScheduleAnyway` on zone and hostname), so nothing else depends on this rule.

`affinity` is permitted in per-location config:
`onlyAllowUserDefinedK8sConfigFields.podSpecConfig.affinity` is `true`.

`safe-to-evict: "false"` is compatible: code servers already request 500m and
2.0Gi, meeting the Autopilot extended-duration minimum, and are not on spot (the
two are mutually exclusive).

**Accepted downside of the timeout change.** A genuinely broken deployment, such
as a crash-looping container, now takes 900s to surface rather than 300s. Broken
images are unaffected, handled separately by `imagePullGracePeriod` at its 30s
default.

Items 1 and 2 are Helm and need `helm upgrade`. Item 3 ships through the normal
per-location deploy and will redeploy all five locations.

### Phase 2: warm capacity

Reserve pre-provisioned arm64 capacity so code-server placement does not wait on
NAP. This is the balloon-pod pattern Google documents for Autopilot.

Two objects:

- A `PriorityClass` with a negative value (`-10`), `globalDefault: false`, and
  `preemptionPolicy: Never` so the placeholder never displaces anything itself.
- A `Deployment` of placeholder pods running `pause`, with requests matching a
  code server (500m cpu, 2Gi memory), the same `Scale-Out` plus `arm64`
  `nodeSelector`, and labels `managed_by: K8sUserCodeLauncher` plus
  `deployment_name: prod`.

Because the placeholder ranks below everything, a code server preempts it
immediately and takes its node with no provisioning wait. The displaced
placeholder goes `Pending`, which triggers NAP to build a replacement node in
the background and re-warm the buffer.

**The label choice reserves the buffer for code servers.** Carrying
`managed_by: K8sUserCodeLauncher` and `deployment_name: prod` while deliberately
omitting `location_name` means run pods treat those nodes as code-server nodes
and stay off them, while a code server can still land there because its
self-anti-affinity keys on `location_name`, which the placeholder lacks. The
isolation is preserved rather than weakened.

The same omission keeps the placeholder out of the per-location PDB selectors,
which match all three labels. It will match the code-server
`topologySpreadConstraints` selector, which is `ScheduleAnyway` and therefore
advisory.

**Sizing is a cost decision.** The logs show four locations relocating within
the same second, so a single placeholder does not cover the observed worst case.
Start at two and let measurement drive the number rather than paying for five up
front. Cost is continuous under pod-based billing and should be priced before
committing.

**This phase is gated.** Do not land it until all three are verified against the
live cluster:

1. Autopilot Warden admits a negative-priority pod. Warden has already rejected
   Custom ComputeClasses and multi-value `nodeSelector` entries in this repo, so
   this is a real risk rather than a formality.
1. The warm node survives cluster-autoscaler consolidation. If the node is
   reclaimed, the buffer is worthless. Whether the placeholder needs
   `safe-to-evict: "false"` to pin its node is part of this check.
1. A code server actually preempts a placeholder in practice, rather than
   queueing alongside it.

`.k8s/CLAUDE.md` currently states that Autopilot node pre-warming is not
possible. That is accurate about DaemonSets and image pre-pulling but
understates the case: the balloon-pod approach is a workload pattern, not a
node-lifecycle API. The line needs correcting.

### Phase 3: auto-recovery watchdog

Phases 1 and 2 reduce failure probability. Neither eliminates it — an arm64
stockout longer than the timeout still produces a terminal `ERROR`. This phase
removes the human intervention.

A scheduled GitHub Actions workflow on roughly a 10 minute cadence. It must live
outside both the cluster and Dagster, because a Dagster sensor could itself be
in the failed location.

Logic:

1. Query the Dagster+ control plane for locations whose `loadStatus` is `ERROR`.
1. Retry only when the error matches the infrastructure signature: the message
   contains both `Timed out waiting for deployment` and `FailedScheduling`. A
   genuine import error or bad image has a different shape and must be left to
   fail loudly, because it needs a human.
1. Skip when a deploy is already in flight, judged by
   `codeLocationUpdateTriggerTimestamp` recency, so the watchdog cannot race a
   deploy.
1. Cap attempts by counting consecutive matching `ERROR` entries in the
   location's load history. This keeps the watchdog stateless and
   self-correcting, with no external state to maintain.
1. Past the cap, stop retrying and fail the workflow so it notifies rather than
   looping silently.

The workflow needs `DAGSTER_CLOUD_API_TOKEN`, already a repository secret. Scope
it to the job that uses it, consistent with the existing convention in
`.github/CLAUDE.md`.

**Open question that gates this phase.** Whether triggering a reload genuinely
re-attempts deployment for an errored location, or only re-reads a cached
snapshot. The whole phase depends on it and it is not yet verified. Establish
this first, against a location deliberately put into the timeout state.

## Failure modes

| Risk                                             | Mitigation                                                                                                                     |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| Watchdog masks a real code defect                | Signature gate plus attempt cap; genuine errors do not match and are never retried                                             |
| Watchdog races a deploy                          | Skip when `codeLocationUpdateTriggerTimestamp` is recent                                                                       |
| Placeholder starves real workloads               | Negative priority plus `preemptionPolicy: Never`; it can never displace anything                                               |
| Warm node reclaimed by autoscaler                | Gate item 2 above; pin with `safe-to-evict` if needed                                                                          |
| Longer timeout delays real-failure feedback      | Accepted; bad images still surface at 30s via `imagePullGracePeriod`                                                           |
| Rollover co-locates two code servers on one node | Only under `preferred`; node must fit two 500m/2Gi pods or the scheduler picks elsewhere, which is the current behavior anyway |

## Verification

Baseline is the four-week table above. After each phase, re-measure the same six
counters over at least one week and compare.

Success criteria:

- Zero `loadStatus: ERROR` entries carrying the timeout signature.
- `FailedScheduling` on code-server pods materially below the 213 to 472 band.
- Agent gRPC errors below the 85 to 134 per week band.
- `Evicted` still 0, confirming the isolation was not weakened.

Per-phase checks:

- Phase 1: confirm the new timeout is live via the agent Deployment spec after
  `helm upgrade`; confirm all five locations reload cleanly after the
  `dagster-cloud.yaml` change.
- Phase 2: the three gate items, then confirm a code-server rollover schedules
  in seconds rather than minutes.
- Phase 3: force a location into the timeout state, confirm the watchdog
  recovers it, then confirm it does **not** retry a deliberately broken import.

## Out of scope

- Raising code-server priority. Declined.
- Relaxing the run-pod-to-code-server anti-affinity. Incident-motivated.
- The `kipptaf__google__bigquery__table_modified_sensor` timeout, tracked in
  [#4908](https://github.com/TEAMSchools/teamster/issues/4908) and fixed in
  [#4913](https://github.com/TEAMSchools/teamster/pull/4913). It shares the
  exception class but has an unrelated cause.
- The absence of `kipptaf__google__bigquery__table_modified_sensor` from
  `docs/reference/automations.md`. Pre-existing and unrelated; the generator
  appears to omit sensors that emit asset events rather than run requests.

## Documentation changes

`.k8s/CLAUDE.md`, required regardless of which phases land:

- Add `deploymentStartupTimeout` to the "Timeout types (do not conflate)"
  section. The section currently documents only `serverProcessStartupTimeout`,
  and that gap led to identifying the wrong knob during this investigation.
- Correct the "Autopilot node pre-warming: Not possible" line.
- Record that a timed-out code-server deployment does not retry, so the
  operational consequence is understood without re-reading the launcher source.
