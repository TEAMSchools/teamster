# CLAUDE.md — `.k8s/`

Helm overrides and deploy scripts for Dagster Cloud agent and 1Password Connect
on GKE Autopilot.

## Conventions

- `values.yaml` is auto-downloaded from Helm — never edit. All customizations go
  in `values-override.yaml`.
- `safe-to-evict: "false"` only blocks cluster autoscaler evictions — kubelet
  node-pressure evictions (exit 137, OOM) are unaffected. Scale-Out density
  makes these occasional; Dagster retries automatically.
- GKE Autopilot cluster: `autopilot-cluster-dagster-hybrid-1` in `us-central1`
  (`kubectl config current-context`).
- **Scheduling strategy** uses weighted `nodeAffinity` preferences (no hard
  `nodeSelector`). Compute-class tiers: Scale-Out arm64 > General-Purpose >
  Scale-Out x86 > Balanced. Spot adds +50 on agent and code server pods (not run
  pods — `safe-to-evict: "false"` + spot are mutually exclusive on Autopilot).
  Agent pods exclude arm64 tiers (image is x86-only). Autopilot bills per-pod,
  so fallback tiers have no cost penalty.
- Per-location `server_k8s_config` in `dagster-cloud.yaml` deep-merges with
  global `serverK8sConfig` (Dagster default `K8sConfigMergeBehavior.DEEP`) —
  `podAntiAffinity` from per-location and `nodeAffinity` from global coexist.
- Container images are multi-arch (amd64 + arm64) via Docker buildx matrix in CI
  — x86 fallback works without build changes.
- **Security contexts** on workspace (`serverK8sConfig`) and run
  (`runK8sConfig`) pods: `runAsNonRoot`, UID/GID 1234 (matches Dockerfile
  `teamster` user), `allowPrivilegeEscalation: false`, all capabilities dropped.
  `readOnlyRootFilesystem` intentionally omitted (dbt/Dagster write to `/tmp`).
- **`onlyAllowUserDefinedK8sConfigFields`** restricts what `dagster-cloud.yaml`
  and `dagster-k8s/config` tags can set: `resources`, `env`, `nodeSelector`,
  `affinity`, `annotations`, and `ttlSecondsAfterFinished`. Everything else is
  locked to Helm chart values.
- **Agent topology spread** uses `DoNotSchedule` across
  `topology.kubernetes.io/zone` via `additionalPodSpecConfig`. If multi-zone
  STOCKOUT recurs, relax to `ScheduleAnyway`.
- **Agent readiness probe** checks for
  `/tmp/finished_initial_reconciliation_sentinel.txt`. Rolling update
  (`maxSurge: 200%`, `maxUnavailable: 0%`) ensures zero-downtime Helm upgrades.
