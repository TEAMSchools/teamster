---
name: dagster-k8s-ops
description:
  "Use when a Dagster+ agent or run pod misbehaves on GKE: agent restarts or
  lifecycle, evictions and priority classes, stuck or failed step pods, and
  reading agent errors. Cluster config and Helm values stay in .k8s/CLAUDE.md."
---

# dagster-k8s-ops

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
  `DAGSTER_CLOUD_CLEANUP_SERVER_GRACE_PERIOD_SECONDS` (set to 1500s) and
  `DAGSTER_CLOUD_CLEANUP_SERVER_CHECK_INTERVAL` (set to 600s) control how
  quickly orphaned code server Deployments from previous agent IDs are deleted.
  Do not set grace period below the WORST-CASE first reconcile, which is
  `deploymentStartupTimeout` + `serverProcessStartupTimeout` = 1200s, not the
  ~3-4 min a healthy reconcile takes. Below that, an orphaned code server can be
  deleted before its replacement is reconciled. Asserted in
  `tests/test_k8s_config.py` alongside the readinessProbe budget, which is sized
  against the same number.
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
- **Do NOT add `safe-to-evict: "false"` to code server pods.** Tried 2026-08-18
  to stop the 38-59 weekly autoscaler relocations, reverted the same day
  (#4921). Because it blocks only autoscaler eviction and NOT scheduler
  preemption, pinning a priority-0 pod removes the graceful way to free its node
  and leaves only the violent one: capacity fragments, then run pods
  (priority 1000) preempt code servers to obtain it — and every preemption
  recreates the Service with a fresh ClusterIP, which is the churn the
  annotation was meant to reduce. Measured at matched load (~32 run/step pods
  per 15 min): with it, 18-20 agent gRPC errors and 8-9 `Preempted` per 15 min;
  without it, 0 and 0 across 12 hours including the nightly wave. **General
  rule: pinning a low-priority pod against the autoscaler converts graceful
  relocation into preemption.** The agent and run pods keep the annotation —
  nothing outranks them the way run pods outrank code servers. Absence is
  asserted in `tests/test_k8s_config.py`.
- **Judge a scheduling change only against matched run-pod load.** Code-server
  churn tracks run-pod volume, so a quiet window reads as success and a busy one
  as regression. Count `Scheduled` events on `dagster-run-` / `dagster-step-`
  pods for the same window and discard readings below ~25 per 15 min. Two zero
  readings during the #4921 investigation were load artifacts, not fixes.
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
- **Timeout types** (do not conflate). Three distinct waits, in the order they
  occur:
  1. **Deployment startup** (`deploymentStartupTimeout`, Helm `workspace` key,
     chart default 300s, set to 900s) — agent waits for the code server
     Deployment to become ready, i.e. for the pod to be SCHEDULED. This is the
     one that fires during a NAP `FailedScheduling` wait, and its failure
     message is `Timed out waiting for deployment {name}` with
     `Pod status: Pending`. Governs `wait_for_deployment_complete`, not
     `_wait_for_dagster_server_process`.
  1. **Server process startup** (`serverProcessStartupTimeout`, Helm `workspace`
     key, default 180s, set to 300s) — agent waits for a gRPC ping AFTER the
     Deployment exists. Fires when Dagster definitions are slow to import, not
     when the pod cannot be placed.
  1. **Sensor execution** (300s, Dagster+ deployment setting) — sensor ran too
     long; the code server stays up and no churn results.
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
- **Autopilot node pre-warming**: no node-lifecycle control — no DaemonSets, no
  image pre-pulling, no cordon that holds. But capacity CAN be reserved at the
  workload layer with balloon pods: a Deployment of placeholder pods on a
  negative `PriorityClass` holds nodes that real pods preempt instantly, and the
  displaced placeholder then triggers NAP to re-warm the buffer. Google
  documents this for Autopilot. Not deployed here yet; see
  `docs/superpowers/specs/2026-08-18-code-server-scheduling-resilience-design.md`
  Phase 2, gated on verifying Warden admits a negative priority value.
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
- **A timed-out code server deployment is TERMINAL — the agent never retries
  it.** `_should_trigger_recovery` in
  `dagster_cloud/workspace/user_code_launcher/user_code_launcher.py` returns
  `False` when the location is in `control_plane_error_locations` ("control
  plane agrees there is an error, don't retry"). Recovery fires only when the
  agent holds a local error while the control plane believes the location is
  healthy. Normal reconciliation redeploys only when
  `actual_entry.update_timestamp != desired_entry.update_timestamp`, which
  changes on a new deploy, and the periodic health check needs a running
  endpoint that a never-started pod does not have. So a location that fails to
  schedule stays `ERROR` until someone pushes a commit or clicks redeploy. No
  agent setting changes this;
  `DAGSTER_CLOUD_DISABLE_LOCAL_ERROR_SERVER_RECOVERY` only turns recovery off.
