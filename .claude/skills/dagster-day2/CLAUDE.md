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
