# CLAUDE.md — `.k8s/`

Helm overrides and deploy scripts for Dagster Cloud agent and 1Password Connect
on GKE Autopilot. Agent lifecycle, eviction and priority, troubleshooting, and
agent error observability are incident runbooks: invoke the `dagster-k8s-ops`
skill.

## Cluster

- GKE Autopilot: `autopilot-cluster-dagster-hybrid-1` in `us-central1`
  (`kubectl config current-context`).
- **`kubectl` from the Claude Bash tool is classifier-blocked regardless of
  in-conversation consent** — even read-only `kubectl config current-context`.
  Hand cluster ops (`kubectl apply` of 1Password items, secret-key verification)
  to the user, like `git push origin main`; don't retry.
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
- `deploymentStartupTimeout` (Helm `workspace` key, chart default 300s) — time
  the agent waits for the code server Deployment to become ready, i.e. for the
  pod to be SCHEDULED. Currently set to 900s. This is the timeout that fires
  during a NAP `FailedScheduling` wait. Raising it also raises the agent's
  worst-case first reconcile, so the `readinessProbe` `failureThreshold` and
  `DAGSTER_CLOUD_CLEANUP_SERVER_GRACE_PERIOD_SECONDS` must move with it, along
  with `install.sh`'s `rollout status --timeout`.
- `serverProcessStartupTimeout` (Helm `workspace` key, default 180s) — time the
  agent waits for a code server gRPC ping after the Deployment exists. Fires on
  slow definitions import, not on failed placement. Currently set to 300s in
  `values-override.yaml`.

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
Custom (user-added) text fields sync under their label verbatim (verified:
numeric DeansList school-id labels → keys `121`, `966`); the remaps above only
hit built-in login/SFTP-template fields.

## Security

- **Security contexts** on workspace (`serverK8sConfig`) and run
  (`runK8sConfig`) pods: `runAsNonRoot`, UID/GID 1234 (matches Dockerfile
  `teamster` user), `allowPrivilegeEscalation: false`, all capabilities dropped.
  `readOnlyRootFilesystem` intentionally omitted (dbt/Dagster write to `/tmp`).
- **`onlyAllowUserDefinedK8sConfigFields`** restricts what `dagster-cloud.yaml`
  and `dagster-k8s/config` tags can set: `resources`, `env`, `volumeMounts`,
  `nodeSelector`, `affinity`, `volumes`, `annotations`, and
  `ttlSecondsAfterFinished`. Everything else is locked to Helm chart values.

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
