# Dagster Run/Step Pod PriorityClass

## Problem

During GKE cluster memory pressure — typically caused by code location rollover
storms (multiple deployments in quick succession) — kubelet evicts pods to
reclaim resources. Run and step pods have no priority advantage over code server
pods, making them equally likely to be killed. This causes
`DagsterExecutionInterruptedError`, wasted compute, and forced retries.

The existing `safe-to-evict: "false"` annotation on run pods only blocks
**cluster-autoscaler** eviction, not **kubelet node-pressure** eviction.

### Incident reference

Run `ba0d6a6c-4dbb-495d-a202-8ad1c2075205` (2026-04-03 ~18:08 UTC): step
`kipptaf__dbt_assets` interrupted by SIGTERM while streaming
`dbt run-operation stage_external_sources`. Six `kipptaf-prod-*` code location
pods were killed and replaced between 17:50–17:58, and `Insufficient memory`
FailedScheduling events appeared across all 5 nodes. The automatic retry
succeeded.

## Solution

Create a custom Kubernetes `PriorityClass` and assign it to run/step pods so
kubelet evicts lower-priority pods (code servers) first during memory pressure.

## Components

### 1. PriorityClass manifest

Added to `extraManifests` in `.k8s/dagster/values-override.yaml`:

- **Name:** `dagster-run`
- **Value:** `1000` (above default 0, well below system classes ~1 billion)
- **`globalDefault`:** `false`
- **`preemptionPolicy`:** `PreemptLowerPriority` (default — allows scheduler to
  preempt lower-priority pods to place run pods)

### 2. runK8sConfig update

Add `priorityClassName: dagster-run` to `runK8sConfig.podSpecConfig`. This
covers both pod types:

- **`dagster-run-*`** (run coordinator) — directly from `runK8sConfig`
- **`dagster-step-*`** (step worker) — `K8sStepHandler` inherits
  `podTemplateSpecMetadata` and `podSpecConfig` from `K8sRunLauncher`'s
  `run_k8s_config`

### 3. No changes to agent or code server pods

- **Agent pods** stay at default priority (0). Already protected by
  `safe-to-evict: "false"` (extended-duration).
- **Code server pods** stay at default priority (0). Stateless and PDB-protected
  (`minAvailable: 1` per location).

## Eviction behavior

| Pressure event            | Before                                     | After                                                         |
| ------------------------- | ------------------------------------------ | ------------------------------------------------------------- |
| Kubelet memory pressure   | Run/step pods equally likely to be evicted | Code server pods evicted first; run/step pods survive longer  |
| Autoscaler scale-down     | Blocked by `safe-to-evict: "false"`        | Same (unchanged)                                              |
| Voluntary drain / upgrade | No PDB on run pods                         | Same (Dagster retries handle this)                            |
| Scheduling contention     | All user pods equal                        | Scheduler can preempt code server pods to place run/step pods |

## Risk

Code server pods become more eviction-prone during pressure. If a location's
only code server is evicted, that location's sensors and schedules pause until
the pod is rescheduled. Mitigation: PDBs enforce `minAvailable: 1` per location,
and Autopilot provisions new nodes within ~1-2 minutes.

## GKE Autopilot compatibility

- Custom PriorityClasses are supported on Autopilot.
- Google's extended-duration docs recommend giving important pods the highest
  PriorityClass to survive eviction ordering.
- Pods with priority less than -10 won't trigger node provisioning (not relevant
  here — value is 1000).

## Notes

- `onlyAllowUserDefinedK8sConfigFields.podSpecConfig` does not include
  `priorityClassName`. This is intentional — the allowlist only governs
  per-location overrides via `dagster-cloud.yaml` and `op_tags`. The global
  `runK8sConfig` in Helm values is not restricted by it. No allowlist change is
  needed.

## Changes

| File                                | Change                                    |
| ----------------------------------- | ----------------------------------------- |
| `.k8s/dagster/values-override.yaml` | Add PriorityClass to `extraManifests`     |
| `.k8s/dagster/values-override.yaml` | Add `priorityClassName` to `runK8sConfig` |
| `.k8s/CLAUDE.md`                    | Document PriorityClass in conventions     |
