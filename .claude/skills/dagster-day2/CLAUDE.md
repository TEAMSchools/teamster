# Day-2 Operations

## Targeted agent investigation

When the user asks about a **specific agent ID** (not a general health check),
skip the full day2 skill. Instead:

1. `mcp__dagster__get_cloud_agents(agent_id="<id>")` — filters server-side and
   returns compact JSON. Add `errors_after=<epoch>` to scope errors.
2. Check `list_runs(statuses=["FAILURE"])` in a ±30 min window around the error.
3. Check GKE events in the same window for correlated cluster issues.

Always run all three steps before drawing conclusions — do not stop at step 1
even if the agent looks healthy now. The user is asking you to investigate, not
triage.

## Re-execution chain investigation

Use `get_run_group(run_id)` to get the full re-execution chain for any run in
one call — more efficient than traversing `parentRunId`/`rootRunId` via
`get_run` or `list_runs`.

## Data source for agent errors

Agent-to-cloud communication errors (e.g. `ReadTimeout` to
`*.agent.dagster.cloud`) appear only in the Dagster Cloud agent `errors` array —
not in GKE pod logs or container logs. Always check the agent API first for
these errors.

## gRPC UNAVAILABLE during deploy rollovers is not user-fixable

Tick failures from gRPC UNAVAILABLE during code server pod replacement are
Dagster Cloud platform behavior — no user-side k8s config can eliminate them.
Don't propose fixes; characterize as transient.

## Sensor timeout vs startup timeout

Two unrelated timeout types — do not conflate:

- **Startup timeout** (`serverProcessStartupTimeout`, default 180s): agent waits
  for code server gRPC ping. Failure → agent removes deployment and reconciles a
  replacement. Causes deployment churn.
- **Sensor execution timeout** (300s): sensor function ran too long. Code server
  stays running. Agent logs the error and moves on. No deployment churn.

## Code server startup failure triage

When a code location fails to load, check ALL pods for the deployment — multiple
pod failures indicate a systemic issue. Key signals:

- `Aborted!` on stderr = SIGABRT, native library crash
- `DagsterExecutionInterruptedError` = SIGTERM during import (deploy rollover if
  a new deployment replaced it)
- Silent hang after "Starting Dagster code server" = blocked I/O. Confirm with
  `kubernetes.io/container/cpu/core_usage_time` (`ALIGN_RATE`,
  `alignmentPeriod: "60s"` — the `s` suffix is required): near-zero CPU on a
  Running/Ready pod = I/O block, not CPU throttling.

## Agent health check replacement paths

Four code paths replace a code server — only gRPC UNAVAILABLE uses the grace
period (`DAGSTER_CLOUD_CODE_SERVER_HEALTH_CHECK_REDEPLOY_TIMEOUT`, defaults to
`serverProcessStartupTimeout`). The other three are immediate: error state
(server returns `SerializableErrorInfo`), recovery (agent local error vs Cloud
healthy), and pex disappeared. When the agent logs "300 seconds" but replaces
immediately, it hit an immediate path on the next reconciliation loop.

## Efficient traceback retrieval from Cloud Logging

GKE container tracebacks are split across dozens of individual log entries (one
per line). Search for the exception line first, not the traceback header:
`textPayload:("Exception" OR "Error") AND NOT textPayload:"BetaWarning"` with a
narrow timestamp window. Use `pageSize` 10-15 (50 on per-line entries exceeds
token limits). Skip intermediate frames unless the exception type is ambiguous.

## kipptaf step worker CPU spikes

kipptaf step workers hit the 1000m CPU limit during Python module import. Alerts
on `dagster-step-*` pods for kipptaf jobs that self-resolve within ~60s are this
pattern. Fix via per-asset k8s config overrides, not global limit changes.

## Pod zone placement from VPC firewall logs

`list_log_entries` with `resource.type="gce_subnetwork"` and
`logName=".../compute.googleapis.com%2Ffirewall"` shows `instance.zone` and
`remote_instance.zone` for each connection. Filter on `dest_port=4000` for
agent→code-server gRPC traffic. Agent source IP is consistent across entries.
