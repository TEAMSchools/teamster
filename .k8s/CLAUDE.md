# CLAUDE.md — `.k8s/`

Helm overrides and deploy scripts for Dagster Cloud agent and 1Password Connect
on GKE Autopilot.

## Cluster

- GKE Autopilot: `autopilot-cluster-dagster-hybrid-1` in `us-central1`
  (`kubectl config current-context`).
- `kubectl cordon` is ineffective on Autopilot — Google manages node lifecycle
  and may ignore cordon or replace the node entirely.

## Helm

- `values.yaml` is auto-downloaded from Helm — never edit. All customizations go
  in `values-override.yaml`.
- **Helm upgrades are manual** — `git push` triggers Dagster Cloud code location
  image builds, not Helm agent upgrades. Agent config changes in
  `values-override.yaml` require a manual `helm upgrade`.
- `serverProcessStartupTimeout` (Helm `workspace` key, default 180s) — time the
  agent waits for a code server gRPC ping after creating the Deployment.
  Currently set to 300s in `values-override.yaml`.

## Scheduling

- Weighted `nodeAffinity` preferences (no hard `nodeSelector`). Compute-class
  tiers: Scale-Out arm64 > General-Purpose > Scale-Out x86 > Balanced. Spot adds
  +50 on code server pods (not agent or run pods). Autopilot bills per-pod, so
  fallback tiers have no cost penalty.
- Agent pods use `safe-to-evict: "false"` (extended-duration) to prevent
  Autopilot scale-down churn, which is mutually exclusive with spot. Agent pods
  exclude arm64 tiers (image is x86-only).
- **Agent topology spread** uses `ScheduleAnyway` across
  `topology.kubernetes.io/zone` via `additionalPodSpecConfig`. Prefers
  cross-zone but allows same-zone during capacity exhaustion.

## Security

- **Security contexts** on workspace (`serverK8sConfig`) and run
  (`runK8sConfig`) pods: `runAsNonRoot`, UID/GID 1234 (matches Dockerfile
  `teamster` user), `allowPrivilegeEscalation: false`, all capabilities dropped.
  `readOnlyRootFilesystem` intentionally omitted (dbt/Dagster write to `/tmp`).
- **`onlyAllowUserDefinedK8sConfigFields`** restricts what `dagster-cloud.yaml`
  and `dagster-k8s/config` tags can set: `resources`, `env`, `volumeMounts`,
  `nodeSelector`, `affinity`, `volumes`, `annotations`, and
  `ttlSecondsAfterFinished`. Everything else is locked to Helm chart values.

## Agent Lifecycle

- Container images are multi-arch (amd64 + arm64) via Docker buildx matrix in CI
  — x86 fallback works without build changes.
- **Agent image architecture**: `dagster/dagster-cloud-agent` is amd64-only (as
  of 1.12.22). Check with
  `curl -s "https://hub.docker.com/v2/repositories/dagster/dagster-cloud-agent/tags/?page_size=3"`.
  `docker` CLI is not available in codespace.
- **Agent readiness probe** checks for
  `/tmp/finished_initial_reconciliation_sentinel.txt`. Rolling update
  (`maxSurge: 200%`, `maxUnavailable: 0%`) ensures zero-downtime Helm upgrades.
- **Orphan cleanup env vars** —
  `DAGSTER_CLOUD_CLEANUP_SERVER_GRACE_PERIOD_SECONDS` (set to 900s) and
  `DAGSTER_CLOUD_CLEANUP_SERVER_CHECK_INTERVAL` (set to 600s) control how
  quickly orphaned code server Deployments from previous agent IDs are deleted.
  Do not set grace period below reconciliation time (~3-4 min).

## Eviction and Priority

- `safe-to-evict: "false"` only blocks cluster autoscaler evictions — kubelet
  node-pressure evictions (exit 137, OOM) are unaffected. Scale-Out density
  makes these occasional; Dagster retries automatically.
- **PriorityClass `dagster-run`** (value 1000) on run/step pods makes kubelet
  evict code server pods (default priority 0) first during node memory pressure.
- **PriorityClass `dagster-agent`** (value 1000) on agent pods — same tier as
  run/step pods, preventing mutual preemption. Does not protect against OOM
  kills of the pod itself — only eviction ordering. Code servers tolerate
  eviction: they are stateless and PDB-protected (`minAvailable: 1`).
- **PDB for code servers** uses `minAvailable: 1` (not `maxUnavailable`).
  `maxUnavailable` requires resolving the owning controller (Deployment) to
  calculate expected pod count — during Dagster Cloud rollovers the old
  Deployment is deleted before pods terminate, causing
  `CalculateExpectedPodCountFailed` and leaving pods unprotected. `minAvailable`
  only counts current healthy pods, no controller lookup needed.

## gRPC Worker Threads

`DAGSTER_GRPC_MAX_WORKERS` (env var on code server pods via
`serverK8sConfig.containerConfig.env`) sets the gRPC thread pool size. Each
sensor eval, schedule eval, and health check holds one thread for its duration.
Unset default is `min(32, cpu_count + 4)` — ~5 on 0.5 vCPU pods, too low for
locations with many sensors. Currently set to 20 globally.

Sizing: sensors + (peak concurrent schedules / 3) + 3 headroom. Idle threads
cost ~1MB each, zero CPU (GIL). Changes require `helm upgrade` (see Helm
section) and only take effect on **new** code server pods — existing pods must
be recycled.

## Resource Config Inheritance

Three pod types, three config sources:

| Pod type        | Name pattern        | Base config                                                                        | Override                                           |
| --------------- | ------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------- |
| Code server     | `<location>-prod-*` | `serverK8sConfig` (Helm) + per-location `server_k8s_config` (`dagster-cloud.yaml`) | —                                                  |
| Run coordinator | `dagster-run-*`     | `runK8sConfig` (Helm) + per-location `run_k8s_config` (`dagster-cloud.yaml`)       | —                                                  |
| Step worker     | `dagster-step-*`    | same as run coordinator                                                            | `op_tags["dagster-k8s/config"]` deep-merges on top |

"Same as run coordinator" includes annotations, priorityClassName, and affinity
— `K8sStepHandler` inherits the full `run_k8s_config` from `K8sRunLauncher`.

Per-location `server_k8s_config` in `dagster-cloud.yaml` deep-merges with global
`serverK8sConfig` (Dagster default `K8sConfigMergeBehavior.DEEP`) —
`podAntiAffinity` from per-location and `nodeAffinity` from global coexist.

`op_tags` at or below the `runK8sConfig` limit are redundant — remove them when
bumping the base. CPU limits live in three places: Python `op_tags` dicts, YAML
config files (`config/*.yaml`), and Helm values. Scan all three when changing
defaults.

## Troubleshooting

- **Code location down**: Use `list_code_locations` (Dagster MCP) for the error
  summary, then **GKE pod logs** (`mcp__gke__query_logs`) for the full picture.
  The `list_code_locations` error only shows the last 25 log lines from the pod
  — always check GKE logs for the complete timeline.
- **Dagster Cloud deployment model**: Each deploy creates a new k8s Deployment
  (`<location>-prod-<hash>`). Old Deployments are deleted during rollover.
  Multiple commits in quick succession → multiple deployments → pods competing
  for resources.
- **GKE log queries**: Filter by `resource.labels.pod_name:<prefix>` for
  container logs, `resource.type="k8s_cluster"` for k8s events (scheduling,
  scaling, eviction). Use `jsonPayload.reason` to filter event types.
- **Pathlib `AttributeError` on code server startup**: `PosixPath` missing
  `_str`/`_drv` slots = SIGTERM hit during Python module import (preemption or
  eviction). Pods self-heal on restart. Safe to mute in GCP Error Reporting.
- **GCP Error Reporting investigation**: `list_group_stats` (find groups) →
  `list_log_entries` (reconstruct multi-line tracebacks from individual log
  entries) → `k8s_pod` events (find root cause: preemption, OOM, eviction).
