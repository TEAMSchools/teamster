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

## Data source for agent errors

Agent-to-cloud communication errors (e.g. `ReadTimeout` to
`*.agent.dagster.cloud`) appear only in the Dagster Cloud agent `errors` array —
not in GKE pod logs or container logs. Always check the agent API first for
these errors.
