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
- **Helm deploy is manual** — editing `values-override.yaml` is fine, but
  changes only take effect after `helm upgrade`. `git push` builds code location
  images, not Helm agent config.
- `serverProcessStartupTimeout` (Helm `workspace` key, default 180s) — time the
  agent waits for a code server gRPC ping after creating the Deployment.
  Currently set to 300s in `values-override.yaml`.

## Scheduling

- **Hard `nodeSelector` on `cloud.google.com/compute-class`** — Autopilot NAP
  only provisions matching nodes for `required` / `nodeSelector` constraints.
  `preferredDuringSchedulingIgnoredDuringExecution` is scheduler scoring applied
  to existing nodes; it does NOT drive provisioning. With only `preferred`, NAP
  falls back to default N4 amd64 and every weighted preference scores 0. Same
  trap for `preferred kubernetes.io/arch: arm64`.
- **One `cloud.google.com/compute-class` value per pod** — Warden
  (`autopilot-compute-class-limitation`,
  `ccc-node-affinity-selector-limitation`) rejects multiple values across ORed
  `nodeSelectorTerms`. Use a Custom ComputeClass with priority-ordered fallbacks
  instead of multi-value affinity.
- **Custom ComputeClasses** in
  [compute-classes.yaml](/.k8s/dagster/compute-classes.yaml):
  `dagster-codeserver` (spot t2a → on-demand t2a → t2d), `dagster-run`
  (on-demand t2a → t2d — no spot, runs are `safe-to-evict: "false"`), and
  `dagster-agent` (t2d only — image is amd64-only, no spot due to
  extended-duration). Built-in classes (`General-Purpose`, etc.) are NOT on this
  cluster's compute-class allowlist — only `Accelerator`, `Balanced`,
  `Performance`, `Scale-Out`, `autopilot`, `autopilot-spot`, and our three CCCs.
  Always reference a CCC by name; do not use built-in class names.
- **Do NOT add Balanced to CCC priorities** — its separation / extended-duration
  minimums (1 vCPU / 4 GiB) exceed our requests (500m / 2 GiB) and would cause
  pod admission rejection if anti-affinity is applied.
- **CCC delivery is manual** —
  `kubectl apply -f .k8s/dagster/compute-classes.yaml`, NOT via Helm
  `extraManifests`. The agent's Helm ServiceAccount lacks cluster-scoped create
  perms on `cloud.google.com/v1/ComputeClass`.
- **`safe-to-evict: "false"` (extended-duration) is on agent and run pods.** It
  is the only autoscaler-eviction guard — `podAntiAffinity` is placement,
  `dagster-agent` PriorityClass blocks lower-priority preemption only. GKE
  silently drops extended-duration when a pod targets a CCC ("You can't request
  extended run times for Pods that target custom compute classes") and Warden
  emits a warning — so on this cluster, autoscaler-eviction protection for both
  agent and run pods is unspecified. We accept the warning; the annotation also
  blocks accidental moves to a spot tier (extended-duration is mutually
  exclusive with spot). Run pods have a real secondary guard via
  `podFailurePolicy` (`DisruptionTarget` → `Ignore`) — the agent does not.
  **Watch for unexpected scale-down churn on agent reconciliation** (Service /
  Deployment recreation across all code locations) — if it fires, the trade is
  to drop the CCC nodeSelector (revert to default Autopilot placement) or drop
  the annotation (lose autoscaler-eviction guard for explicit machine family).
- **Agent topology spread** uses `ScheduleAnyway` across
  `topology.kubernetes.io/zone` via `additionalPodSpecConfig` — prefers
  cross-zone but allows same-zone during capacity exhaustion (do not switch to
  `DoNotSchedule`, which would block agent rollouts when one zone is full).

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
- **Code server ClusterIPs change on every reconcile** —
  `unique_resource_name()` in
  `dagster_cloud/workspace/user_code_launcher/utils.py` appends a fresh
  `uuid4().hex[:6]`; Services are delete-old/create-new, never updated in place.
  Multiple distinct gRPC IPs across tick errors in a short window = agent
  reconciliation, NOT pod preemption. Audit-log signal:
  `protoPayload.methodName="io.k8s.core.v1.services.create"` on `dagster-cloud`
  namespace.
- **`dagsterCloudAgent.replicas: 2` doubles Service churn** — both replicas race
  and independently recreate Services per control-plane update. Agent HA trades
  directly against reduced ClusterIP churn; currently set to 1.

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
- **GKE Autopilot system-critical preemption** — `system-cluster-critical` and
  `system-node-critical` pods (priority 2,000,000,000) preempt dagster-run pods
  (priority 1000) cluster-wide whenever GKE needs to land kube-dns, fluent-bit,
  metrics-agent, etc. on a node. Unpreventable at our layer. Observable
  signature in pod events: "Preempted in order to admit critical pod". Mitigated
  by `runK8sConfig.jobSpecConfig.podFailurePolicy` with `action: Ignore` on the
  `DisruptionTarget` pod condition — preempted pods transparently retry without
  burning `backoffLimit`.

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

**`jobSpecConfig` accepts any K8s Job spec field** via Dagster's `Permissive()`
schema in `UserDefinedDagsterK8sConfig`. snake_case/camelCase handled
automatically by `k8s_snake_case_dict` → `k8s_model_from_dict`. Including newer
fields like `podFailurePolicy` (K8s 1.31+ GA) that aren't in Dagster's typed
schema. Dagster default `backoffLimit` is **0** (not K8s default 6) —
`DEFAULT_K8S_JOB_BACKOFF_LIMIT` in `dagster_k8s/job.py`.

## Pod Labels (for selectors / PDBs / anti-affinity)

From `dagster_k8s/utils.py` `get_common_labels()` — applied to both run and step
pods:

| Key                           | Value                                       |
| ----------------------------- | ------------------------------------------- |
| `app.kubernetes.io/name`      | `dagster`                                   |
| `app.kubernetes.io/instance`  | `dagster`                                   |
| `app.kubernetes.io/part-of`   | `dagster`                                   |
| `app.kubernetes.io/component` | `run_worker` (run) / `step_worker` (step)   |
| `dagster/run-id`              | run UUID (both)                             |
| `dagster/code-location`       | location name if `remote_job_origin` is set |

Code server pods (`<location>-prod-*`) carry `managed_by: K8sUserCodeLauncher`,
`deployment_name: prod`, `location_name: <loc>` — already used by the
per-location PDB selectors in `extraManifests`.

Agent pods (`user-cloud-dagster-cloud-agent-*`) carry
`app.kubernetes.io/name: dagster-cloud-agent`.

**Self-exclusion pitfall on run/step anti-affinity**: do NOT use
`app.kubernetes.io/name: dagster` as an anti-affinity `labelSelector` ON a
run/step pod — that label is on the pod itself, so the selector would self-match
and block scheduling everywhere. Use code-server-specific labels
(`managed_by: K8sUserCodeLauncher`) or agent-specific labels
(`app.kubernetes.io/name: dagster-cloud-agent`) when the anti-affinity target is
a different pod type.

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
  container logs. For k8s events (log_name `.../logs/events`), resource type
  depends on event scope: pod-level kubelet/scheduler events (`Preempted`,
  `Evicted`, `OOMKilling`, `Killing`) are `resource.type="k8s_pod"`;
  cluster-level events (`ScaleUpFailed`, `FailedScheduling`, `NodeNotReady`,
  `FailedCreate`) are `resource.type="k8s_cluster"`. Use `jsonPayload.reason` to
  filter event types.
- **Pathlib `AttributeError` on code server startup**: `PosixPath` missing
  `_str`/`_drv` slots = SIGTERM hit during Python module import (preemption or
  eviction). Pods self-heal on restart. Safe to mute in GCP Error Reporting.
- **GCP Error Reporting investigation**: `list_group_stats` (find groups) →
  `list_log_entries` (reconstruct multi-line tracebacks from individual log
  entries) → `k8s_pod` events (find root cause: preemption, OOM, eviction).
- **Timeout types** (do not conflate): Startup (`serverProcessStartupTimeout`,
  default 180s) = agent→code server gRPC ping; failure → deployment removed +
  replacement, causes churn. Sensor execution (300s) = sensor ran too long; code
  server stays up, no churn.
- **Code server startup failure signals**: Check ALL pods for the deployment.
  `Aborted!` stderr = SIGABRT (native crash). `DagsterExecutionInterruptedError`
  = SIGTERM during import (rollover). Silent hang after "Starting Dagster code
  server" = blocked I/O — confirm with
  `kubernetes.io/container/cpu/core_usage_time` (`ALIGN_RATE`,
  `alignmentPeriod: "60s"`): near-zero CPU on Running/Ready pod = I/O block.
- **Agent health check replacement paths**: Four paths replace code server. Only
  gRPC UNAVAILABLE uses grace period
  (`DAGSTER_CLOUD_CODE_SERVER_HEALTH_CHECK_REDEPLOY_TIMEOUT` = startup timeout).
  Other three immediate: error state (SerializableErrorInfo), recovery (agent
  local error vs Cloud healthy), pex disappeared. "300 seconds" log + immediate
  replace = hit immediate path on next reconciliation.
- **GKE traceback retrieval**: Tracebacks split across many log entries. Search
  exception line first:
  `textPayload:("Exception" OR "Error") AND NOT textPayload:"BetaWarning"`.
  Narrow timestamp. pageSize 10-15 (50 exceeds tokens on per-line entries).
- **Pod zone placement**: `list_log_entries` with
  `resource.type="gce_subnetwork"` +
  `logName=".../compute.googleapis.com%2Ffirewall"` → `instance.zone` +
  `remote_instance.zone`. Filter `dest_port=4000` for agent→code-server gRPC.
- **Autopilot node pre-warming**: Not possible — no DaemonSets, no image
  pre-pulling, no node lifecycle control. Only levers for cold-node startup
  latency: image size reduction and Dagster timeout increases.
- **CPU limit alert sensitivity**: `GKE Container - High CPU Limit Utilization`
  fires at >90% `ALIGN_MEAN` over 60s with `count=1`. When an asset's `op_tags`
  CPU limit alerts, bump by 250m — re-measure peak with
  `kubernetes.io/container/cpu/core_usage_time` `ALIGN_RATE` before each
  subsequent bump.

## Agent Error Observability

- `get_cloud_agents` errors array capped at **25 per agent** — most recent 25
  only. GCP container logs on `user-cloud-dagster-cloud-agent-agent` pods are
  the complete record.
- Schedule tick evaluation retries gRPC calls indefinitely within a single tick.
  Agent-level "Error serving request" logs during preemption are noise, not tick
  failures. Only `get_tick_history(statuses=["FAILURE"])` reflects terminal
  schedule failures.
- **Hybrid daemon location** — sensor / asset / schedule daemons run in the
  Dagster Cloud control plane, NOT in the local agent. OSS `dagster.yaml`
  settings (`max_tick_retries`, `auto_materialize.*`, etc.) do not apply; the
  Dagster+ full deployment settings (see Dagster+ Deployment Settings section)
  expose no tick-retry knob. Terminal `DagsterUserCodeUnreachableError` ticks
  remain terminal.

## Dagster+ Deployment Settings

`dagster-cloud deployment settings get/set-from-file` — requires
`DAGSTER_CLOUD_API_TOKEN` (not in codespace; user must run or supply token).
Full settings list: `run_monitoring`, `run_retries`, `concurrency`,
`sso_default_role`, `default_sensor_timeout`, `default_schedule_timeout`,
`non_isolated_runs`, `auto_materialize`, `branch_deployments`. The
sensor/schedule timeouts (default 300s) ARE configurable.

`run_monitoring.start_timeout_seconds` only fires for runs in `STARTING` /
`NOT_STARTED` status — does NOT catch dispatch-to-pod-confirmed stalls (run is
already `STARTED` at LAUNCH_RUN dispatch, before pod confirmation).
