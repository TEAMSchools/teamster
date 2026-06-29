# CLAUDE.md — `.k8s/`

Helm overrides and deploy scripts for Dagster Cloud agent and 1Password Connect
on GKE Autopilot.

## Cluster

- GKE Autopilot: `autopilot-cluster-dagster-hybrid-1` in `us-central1`
  (`kubectl config current-context`).
- `kubectl cordon` is ineffective on Autopilot — Google manages node lifecycle
  and may ignore cordon or replace the node entirely.

## Helm

- **`.k8s/setup.sh` is the prerequisite bootstrap for
  `.k8s/dagster/install.sh`** — it installs the
  helm/kubectl/gke-gcloud-auth-plugin toolchain to `~/.local/bin` (no root;
  checksum-verified), runs `gcloud auth login`, fetches cluster credentials, and
  creates the `dagster-cloud` namespace. install.sh is deploy-only;
  `helm: command not found` or `cluster unreachable` means setup.sh wasn't run —
  don't add bootstrap logic to install.sh.
- `values.yaml` is auto-downloaded from Helm — never edit. All customizations go
  in `values-override.yaml`.
- **Helm deploy is manual** — editing `values-override.yaml` is fine, but
  changes only take effect after `helm upgrade`. `git push` builds code location
  images, not Helm agent config.
- `serverProcessStartupTimeout` (Helm `workspace` key, default 180s) — time the
  agent waits for a code server gRPC ping after creating the Deployment.
  Currently set to 300s in `values-override.yaml`.

## Scheduling

- **Hard multi-key `nodeSelector`** — Autopilot NAP only provisions matching
  nodes for `required` / `nodeSelector` constraints. `preferred*` is scheduler
  scoring against existing nodes and does NOT drive provisioning. With only
  `preferred`, NAP falls back to default N4 amd64 and every weighted preference
  scores 0 — same trap for `preferred kubernetes.io/arch: arm64`.
- **Multi-key allowed; multi-value not** — Warden
  (`autopilot-compute-class-limitation`) rejects multiple values for the same
  key but accepts multiple keys. Use `cloud.google.com/compute-class` +
  `kubernetes.io/arch` together to hard-pin both class and CPU architecture.
- **Built-in `Scale-Out` only — do NOT use Custom ComputeClasses (CCCs).** CCCs
  flip the billing model from per-pod (Autopilot pod-based) to per-VM +
  Autopilot Performance Premium (per-vCPU/GiB management fee), even when the
  underlying machine family is the same hardware Scale-Out runs on. Our pods
  don't fill a t2d-standard-4, so we'd pay for empty capacity. CCCs also
  silently drop `safe-to-evict: "false"` (extended-duration).
- **Pod placement** — code server and run pods pin to Scale-Out arm64 (T2A);
  agent pins to Scale-Out amd64 (T2D — image is amd64-only).
- **No fallback — arm64 STOCKOUT will leave code server / run pods Pending.**
  PDB-protected code servers tolerate this (last-good Deployment continues to
  serve). Run pods queue until capacity returns. There is no graceful amd64
  fallback under pod-priced billing — the only route to ordered fallback is
  CCCs, which we rejected on cost. If STOCKOUT becomes recurring, manually flip
  the affected pod's `kubernetes.io/arch` to `amd64` until capacity returns.
- **Do NOT use `Balanced` or `Performance`** — Balanced minimum requests (1 vCPU
  / 4 GiB) exceed ours (500m / 2 GiB). Performance has the same node-based
  pricing penalty as CCCs.
- **`safe-to-evict: "false"` (extended-duration) is on agent and run pods.**
  Under built-in Scale-Out it works as documented — blocks cluster autoscaler
  eviction. Mutually exclusive with spot; do not move agent or run pods to a
  spot tier. Run pods also have `podFailurePolicy` (`DisruptionTarget` →
  `Ignore`) as a secondary guard for non-autoscaler disruptions; the agent does
  not.
- **Spot + built-in Scale-Out + arch is supported under pod-priced billing** —
  set `cloud.google.com/gke-spot: "true"` alongside the compute-class + arch
  nodeSelector; Autopilot auto-injects the toleration. Mutually exclusive with
  `safe-to-evict: "false"`. Code-server spot reclaim triggers full agent
  reconciliation cascade (cold start + ClusterIP churn) — factor into cost
  analysis.
- **Code server topology spread** uses `ScheduleAnyway` across
  `topology.kubernetes.io/zone` via `serverK8sConfig.podSpecConfig` — prefers
  cross-zone but allows same-zone during capacity exhaustion (do not switch to
  `DoNotSchedule`, which would block code-server rollouts when one zone is
  full).

## 1Password Connect secret keys

k8s Secret keys come from the 1Password field's internal name, not the UI label.
Known re-mappings on SFTP items: `password` → `newPassword`, `host` → `url`.
Verify before writing `secretKeyRef.key`:
`kubectl -n dagster-cloud get secret <op-name> -o jsonpath='{.data}' | jq keys`.

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
  eviction: they are stateless and PDB-protected (`maxUnavailable: 1`).
- **PDB for code servers** uses `maxUnavailable: 1`. Do not switch to
  `minAvailable: 1` — GKE Recommender flags single-replica + `minAvailable: 1`
  as blocking voluntary evictions (node maintenance). The known
  `CalculateExpectedPodCountFailed` warning during Dagster Cloud rollovers (old
  Deployment deleted before pods terminate) is acceptable: single-replica
  rollovers are unprotected by definition.
- **PDBs do NOT block spot reclaim** — spot reclaim is involuntary.
- **GKE Autopilot system-critical preemption** — `system-cluster-critical` and
  `system-node-critical` pods (priority 2,000,000,000) preempt dagster-run pods
  (priority 1000) cluster-wide whenever GKE needs to land kube-dns, fluent-bit,
  metrics-agent, etc. on a node. Unpreventable at our layer. Observable
  signature in pod events: "Preempted in order to admit critical pod". Mitigated
  by `runK8sConfig.jobSpecConfig.podFailurePolicy` with `action: Ignore` on the
  `DisruptionTarget` pod condition — preempted pods transparently retry without
  burning `backoffLimit`.
- **Step pod replacement zombie (upstream
  [dagster-io/dagster#33755](https://github.com/dagster-io/dagster/issues/33755))**
  — when `podFailurePolicy: Ignore` spawns a replacement step pod (preemption,
  `TaintManagerEviction`, any `DisruptionTarget`), the replacement hits
  Dagster's `verify_step()` duplicate-start guard, logs
  `Attempted to run <step_key> again even though it was already started. Exiting to prevent re-running the step.`,
  and exits 0. Step state never advances; run hangs until
  `run_monitoring.max_runtime_seconds`. Signature: duplicate
  `StepWorkerStartedEvent` → "already started" `EngineEvent` → silence →
  `RunCancelingEvent` at the max_runtime mark. Don't chase the asset's code or
  query — check the auto-retry; if it succeeded, this was infra disruption, no
  fix needed.
- **`required` antiAffinity authorizes scheduler preemption** of the target pods
  when no other node fits. `runK8sConfig.affinity.podAntiAffinity` is `required`
  against code-server labels, with run pods at priority 1000 vs code-server 0 —
  so the scheduler CAN evict code servers at schedule time, not just kubelet at
  eviction time. Do not describe this anti-affinity as "isolating" code servers
  from runs or "preventing co-location."
- `ttlSecondsAfterFinished` is etcd/apiserver hygiene only — terminated
  containers already released cgroup RSS, so TTL does NOT free node memory. Do
  not propose it as a lever for node memory pressure or eviction issues.

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

`run_monitoring.max_runtime_seconds` (the run-level ceiling, currently
**1800s**) is a deployment-wide default — NOT set per-job in `src/teamster`
(grep finds nothing). Override one job via a `dagster/max_runtime` run tag.
