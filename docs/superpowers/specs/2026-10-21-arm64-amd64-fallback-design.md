# arm64-first, amd64-fallback scheduling for Dagster pods

Issue: #6065

## Why

Run, step, and code server pods are hard-pinned to built-in Scale-Out arm64
(T2A). When Google runs out of T2A capacity in `us-central1`, those pods sit
`Pending`. A run that cannot start within Dagster+'s 600-second start timeout
fails with "Run timed out due to taking longer than 600 seconds to start". It
gets one immediate retry, which usually hits the same stockout. In one burst on
2026-10-20, 42 of the last 50 failed runs had never started, and every run that
did not retry had already used its retry.

The cost that matters is human: someone has to notice the failed runs and rerun
them. The fix is to give the pods somewhere else to go. When arm64 is out, they
should run on amd64 instead of waiting.

## Goal

Run, step, and code server pods prefer arm64 nodes and fall back to amd64 nodes
automatically when GKE cannot provision arm64.

## Non-goals

- Changing the run start timeout, run retry count, or retry rules. (Discussed
  and set aside: the user wants the fallback, not tuning.)
- A Dagster-side relaunch on amd64 (sensor or run tag). Rejected by the user.
- Moving the agent. It stays on built-in Scale-Out amd64, because its image is
  amd64-only.
- Cleaning up the existing unused custom classes `dagster-agent`,
  `dagster-codeserver`, and `dagster-run` in the cluster.
- Alerting on fallback events.

## Anti-goals

- Any pod that can be evicted mid-run by the cluster autoscaler. The
  `safe-to-evict: "false"` annotation exists so step pods are not interrupted
  mid-flight, and it must keep working on the new class.
- Per-VM billing. Paying for whole nodes our small pods do not fill is the
  reason custom ComputeClasses were rejected before.

## Design

### The ComputeClass

One custom GKE ComputeClass, named `dagster-arm-first`, using `podFamily`
priority rules:

```yaml
apiVersion: cloud.google.com/v1
kind: ComputeClass
metadata:
  name: dagster-arm-first
spec:
  autopilot:
    enabled: true
  priorities:
    - podFamily: general-purpose-arm
    - podFamily: general-purpose
```

- `spec.autopilot.enabled: true` is required on this cluster. Without it, GKE
  rejects the class ("pod family can be used only if Autopilot is enabled").
- `podFamily` rules need GKE 1.35.3-gke.1389000 or later for
  `general-purpose-arm`. The cluster is on 1.35.8-gke.1439001.
- Pods on `podFamily` rules are billed per pod, not per VM (GKE docs, "About
  Autopilot mode workloads in GKE Standard"). This is what makes a custom class
  acceptable now when it was not before.
- Ship it through the Helm chart's `extraManifests` list in
  `.k8s/dagster/values-override.yaml`, next to the existing PDBs. It is
  cluster-scoped. No new deploy path.

### Pod placement

Code server (`serverK8sConfig.podSpecConfig`) and run/step
(`runK8sConfig.podSpecConfig`) pods change from:

```yaml
nodeSelector:
  cloud.google.com/compute-class: Scale-Out
  kubernetes.io/arch: arm64
```

to:

```yaml
nodeSelector:
  cloud.google.com/compute-class: dagster-arm-first
tolerations:
  - key: kubernetes.io/arch
    operator: Equal
    value: arm64
    effect: NoSchedule
```

- The `kubernetes.io/arch` selector must go. Keeping it would pin pods to arm64
  and the fallback could never be used.
- The toleration is needed because arm64 nodes carry a
  `kubernetes.io/arch=arm64:NoSchedule` taint. Autopilot adds the toleration
  automatically only when the pod selects `arm64`, which these pods no longer
  do. Without it, pods could never land on the arm64 tier.
- Step pods inherit `runK8sConfig`, so one change covers run and step pods.
- Everything else on these pods stays as it is: annotations, resources,
  `podFailurePolicy`, anti-affinity, topology spread, priority 0.
- Images are already multi-arch (amd64 and arm64), so no build change is needed.
- No per-location `dagster-cloud.yaml` or `op_tags` sets `nodeSelector` or arch
  today (checked with `rg`), so the Helm values are the only place to change.
- `onlyAllowUserDefinedK8sConfigFields` filters only `dagster-cloud.yaml` and
  run tags, not Helm values, so `tolerations` set in Helm reach the pods. If it
  did not, every pod would silently land on amd64. The post-deploy check ("lands
  on an arm64 node") catches that. (Claude's call.)

### safe-to-evict on the new class (tested)

GKE docs say extended run time is not available for pods on custom compute
classes. The real requirement is narrower: the autoscaler must not evict a pod
mid-run. A live test on this cluster on 2026-10-21 confirmed that it does not:

- A Job pod with `safe-to-evict: "false"` on a `podFamily` class ran alone on an
  underused node for 20+ minutes. The autoscaler never proposed removing the
  node.
- Then an identical Job pod without the annotation ran on the same node. The
  autoscaler evicted it and removed the node about 2 minutes after the pod was
  alone there (`cluster-autoscaler-visibility` log, 17:18:36 UTC).
- Annotated pods were admitted with a warning only. The annotation survived, and
  so did the CPU limits above requests (bursting).

One side effect was found. Autopilot treats the annotation as an
extended-duration request and adds a `cloud.google.com/extended-duration-pods`
key. Warden rejects that key on a pod that also has **node** affinity. Our pods
use `nodeSelector` and **pod** anti-affinity only, so they are not affected.
Adding node affinity to these pods later would break admission.

### Where the arm64 tier lands

In the test, `general-purpose-arm` provisioned `e4a-standard-8` nodes, a
different machine series from T2A. So the arm64 tier itself draws on capacity
other than what ran out. The amd64 tier is a second fallback on top of that.

### Behavior when capacity returns

Pods that fell back to amd64 stay there. Run and step pods finish and go away.
Code servers stay on amd64 until their next redeploy, since `safe-to-evict` also
blocks GKE's active migration back to the higher-priority tier. This is
acceptable.

### Code servers move too (user decision)

Custom classes do not get extended run time, so node upgrades and maintenance
can now drain a code server. The user accepted this trade-off:

- A drained code server comes back by itself. Its Deployment recreates the pod,
  the Service keeps its ClusterIP, and the agent's grace period for gRPC
  UNAVAILABLE covers the restart.
- The bad case is a drain that lands during the agent's metadata upload. That
  leaves the location in a terminal ERROR until someone redeploys, the same way
  as #5187.
- The cluster's maintenance window confines auto-upgrade drains to weekends, and
  uploads mostly follow weekday deploys. So that overlap is narrow.
- Staying on Scale-Out has its own cost. A code server deploy during a stockout
  stays Pending, times out, and lands in that same terminal ERROR, on every
  location deployed during the stockout.

### Co-location with the agent

The agent stays on built-in Scale-Out amd64 at priority 1000. Pods on a
different compute class do not share nodes with it, so a fallen-back code server
never sits where the agent could preempt it. Run pods also keep their required
anti-affinity against the agent.

## Docs, tests, and rules to update

- `.k8s/CLAUDE.md`, _Scheduling_:
  - Replace "Built-in `Scale-Out` only — do NOT use Custom ComputeClasses". The
    per-VM billing and dropped-annotation claims do not hold for `podFamily`
    rules. Keep the warning for machine-family custom classes, which are still
    billed per VM.
  - Replace "Pod placement" and "No fallback" with the new placement.
  - Add the node affinity trap above.
- `.claude/skills/dagster-k8s-ops/SKILL.md` line 76: the agent pins to amd64
  "and the others to arm64". Reword to "the others to the `dagster-arm-first`
  class".
- `tests/test_k8s_config.py`: assert that code server and run pods select the
  `dagster-arm-first` class, carry no `kubernetes.io/arch` selector, and carry
  the arm64 toleration. Also assert that `extraManifests` holds the ComputeClass
  with `general-purpose-arm` before `general-purpose`.
  `test_code_server_requests_meet_scale_out_minimum` names Scale-Out; rename it
  or reword its docstring.
- Comments in `values-override.yaml` that say "Hard-pin to built-in Scale-Out
  arm64 (T2A) ... No fallback" for code servers and run pods.

## Fallback speed (gate before merge)

The live test proved the arm tier provisions and the annotation holds. It did
not measure how long GKE takes to give up on the arm tier and provision
`general-purpose`. If that takes close to 600 seconds, runs still time out and
the goal is missed.

Before merge, the user runs a forced-fallback test. Use a throwaway class whose
first rule cannot be provisioned in `us-central1`, followed by
`podFamily: general-purpose`. Time a Job pod from creation to `Running`.

- Well under 600 seconds: proceed.
- Near or over 600 seconds: stop and revisit, for example by raising
  `run_monitoring.start_timeout_seconds` alongside this change.

The builder picks the unsatisfiable first rule. (Claude's call.)

## Rollout

Helm deploys are manual: `.k8s/dagster/install.sh` after merge. That one
`helm upgrade` creates the ComputeClass and changes the agent's pod config. New
run pods and the next code server redeploy pick up the class. Running pods are
not touched.

Check after the deploy:

- `kubectl get computeclass dagster-arm-first` exists.
- A new run's pod shows `cloud.google.com/compute-class: dagster-arm-first` and
  lands on an arm64 node.

## Price

Pods leave Scale-Out for good, so the everyday rate changes, not only the
stockout rate. Rates come from the Cloud Billing Catalog API, `us-central1`, per
hour. The last column is one pod at our 500m / 2 GiB requests.

| Class                                     | vCPU    | GiB      | Pod     |
| ----------------------------------------- | ------- | -------- | ------- |
| Scale-Out arm64 (today)                   | 0.0356  | 0.003938 | 0.0257  |
| `general-purpose-arm` (Autopilot Arm Pod) | 0.03216 | 0.00352  | 0.0231  |
| `general-purpose` x86 (stockout only)     | ~0.0445 | ~0.00492 | ~0.0321 |

The everyday tier is about 10% cheaper than today. The amd64 fallback costs
about 25% more, but only while arm64 is out, and it is still below Scale-Out
x86.

- The x86 `general-purpose` rate is from a third-party site. The catalog query
  missed that SKU.
- The mapping of `general-purpose-arm` to the "Autopilot Arm Pod" SKU is
  inferred from the names. The billing export confirms it a day after the
  2026-10-21 test pods ran.

## Left to the builder

- Exact wording of the updated comments and CLAUDE.md lines.
- Test structure, as long as it follows the existing style in
  `tests/test_k8s_config.py`.
