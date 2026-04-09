# Day-2 Operations

## Targeted agent investigation

Specific agent ID query (not general health): skip full skill.

1. `get_cloud_agents(agent_id="<id>", errors_after=<epoch>)`
2. `list_runs(statuses=["FAILURE"])` ±30 min around error
3. GKE events same window

Run all three before concluding — even if agent looks healthy now.

## Re-execution chains

`get_run_group(run_id)` → full chain in one call. Don't traverse
parentRunId/rootRunId via get_run/list_runs.

## Agent error data source

ReadTimeout to `*.agent.dagster.cloud` only appears in agent `errors` array —
not in GKE pod/container logs. Check agent API first.

## gRPC UNAVAILABLE tick failures

Two causes:

- **Deploy rollover** (transient): brief clusters bounded by successes,
  self-resolving.
- **Health check starvation** (actionable): long sensor evals block gRPC threads
  → sustained failures + pod replacement loops. Diagnose: agent logs "failed a
  health check … 300 seconds" + SuccessfulCreate frequency. Fix:
  `DAGSTER_GRPC_MAX_WORKERS`. See dagster-io/dagster#25116.

## Timeout types (do not conflate)

- **Startup** (`serverProcessStartupTimeout`, default 180s): agent→code server
  gRPC ping. Failure → deployment removed + replacement. Causes churn.
- **Sensor execution** (300s): sensor ran too long. Code server stays up. No
  churn.

## Code server startup failure signals

Check ALL pods for the deployment. Key signals:

- `Aborted!` stderr = SIGABRT (native crash)
- `DagsterExecutionInterruptedError` = SIGTERM during import (rollover)
- Silent hang after "Starting Dagster code server" = blocked I/O. Confirm:
  `kubernetes.io/container/cpu/core_usage_time` (`ALIGN_RATE`,
  `alignmentPeriod: "60s"`): near-zero CPU on Running/Ready pod = I/O block.

## Agent health check replacement paths

Four paths replace code server. Only gRPC UNAVAILABLE uses grace period
(`DAGSTER_CLOUD_CODE_SERVER_HEALTH_CHECK_REDEPLOY_TIMEOUT` = startup timeout).
Other three immediate: error state (SerializableErrorInfo), recovery (agent
local error vs Cloud healthy), pex disappeared. "300 seconds" log + immediate
replace = hit immediate path on next reconciliation.

## GKE traceback retrieval

Tracebacks split across many log entries. Search exception line first:
`textPayload:("Exception" OR "Error") AND NOT textPayload:"BetaWarning"`. Narrow
timestamp. pageSize 10-15 (50 exceeds tokens on per-line entries).

## kipptaf step worker CPU

kipptaf steps hit 1000m CPU during import. `dagster-step-*` alerts self-resolve
~60s. Fix: per-asset k8s config, not global limit.

## Data caveats

`get_location_load_history` returns N most recent deploys regardless of
timestamp. Distinguish in-window vs historical.

## Temporal correlation

Signals in same window ≠ causal. Compare timestamps before grouping. Run failure
at 04:00 + alert at 06:00 = independent.

## Agent preemption by run pods

Agents at priority 0 preempted by run/step pods at 1000 (`dagster-run`).
`safe-to-evict`/PDBs don't block priority preemption. Symptoms: all-location
`gRPC UNAVAILABLE`, "no agents have recently heartbeated", many
SuccessfulCreate+Preempted on agent pods. Fix: agent PriorityClass = 1000.

## Pod zone placement

`list_log_entries` with `resource.type="gce_subnetwork"` +
`logName=".../compute.googleapis.com%2Ffirewall"` → `instance.zone` +
`remote_instance.zone`. Filter `dest_port=4000` for agent→code-server gRPC.
