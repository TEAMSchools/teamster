# Day-2 Operations

## Targeted agent investigation

When the user asks about a **specific agent ID** (not a general health check),
skip the full day2 skill. Instead:

1. `mcp__dagster__get_cloud_agents()` — response is 200KB+, always saved to
   file. Filter with Python inline for the specific agent ID (faster than
   `filter_agents.py` which processes all agents).
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

## Efficient traceback retrieval from Cloud Logging

GKE container tracebacks are split across dozens of individual log entries (one
per line). Search for the exception line first, not the traceback header:
`textPayload:("Exception" OR "Error") AND NOT textPayload:"BetaWarning"` with a
narrow timestamp window. Use `pageSize` 10-15 (50 on per-line entries exceeds
token limits). Skip intermediate frames unless the exception type is ambiguous.
