"""Dagster+ MCP tool handlers."""

import json
from typing import Annotated, Any, Literal

from pydantic import Field

from .queries import (
    ASSET_CHECK_EXECUTIONS_QUERY,
    ASSET_CONDITION_EVALUATIONS_QUERY,
    ASSET_MATERIALIZATIONS_QUERY,
    ASSET_PARTITION_STATUSES_QUERY,
    BACKFILL_QUERY,
    BACKFILLS_QUERY,
    CAPTURED_LOGS_METADATA_QUERY,
    CODE_LOCATIONS_QUERY,
    COMPUTE_LOGS_QUERY,
    DAEMON_HEALTH_QUERY,
    LAUNCH_MULTIPLE_RUNS_MUTATION,
    LAUNCH_RUN_MUTATION,
    LAUNCH_RUN_REEXECUTION_MUTATION,
    LIST_RUNS_QUERY,
    RUN_BY_ID_QUERY,
    RUN_LOGS_QUERY,
    STALE_ASSETS_QUERY,
    TICK_HISTORY_QUERY,
)
from .server import gql, server

RunStatus = Literal[
    "QUEUED",
    "NOT_STARTED",
    "MANAGED",
    "STARTING",
    "STARTED",
    "SUCCESS",
    "FAILURE",
    "CANCELING",
    "CANCELED",
]

TickStatus = Literal["SUCCESS", "FAILURE", "SKIPPED", "STARTED"]

BackfillStatus = Literal["REQUESTED", "CANCELING", "CANCELED", "FAILED", "COMPLETED"]

ReexecutionStrategy = Literal["FROM_FAILURE", "FROM_ASSET_FAILURE", "ALL_STEPS"]

StalenessCategory = Literal["CODE", "DATA", "DEPENDENCIES"]


def _build_execution_params(
    asset_keys: list[str],
    *,
    repository_location_name: str,
    repository_name: str = "__repository__",
    tags: dict[str, str] | None = None,
    run_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an ExecutionParams dict from asset-centric arguments."""
    params: dict[str, Any] = {
        "selector": {
            "repositoryLocationName": repository_location_name,
            "repositoryName": repository_name,
            "assetSelection": [{"path": key.split("/")} for key in asset_keys],
        },
    }
    if run_config:
        params["runConfigData"] = run_config
    if tags:
        params["executionMetadata"] = {
            "tags": [{"key": k, "value": v} for k, v in tags.items()],
        }
    return params


@server.tool()
def list_runs(
    limit: Annotated[
        int,
        Field(description="Max number of runs to return (default 20, max 100)."),
    ] = 20,
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous list_runs call."),
    ] = None,
    job_name: Annotated[
        str | None,
        Field(description="Filter to runs for this job name."),
    ] = None,
    run_ids: Annotated[
        list[str] | None,
        Field(description="Filter to specific run IDs."),
    ] = None,
    statuses: Annotated[
        list[RunStatus] | None,
        Field(description="Filter to runs with these statuses."),
    ] = None,
    tags: Annotated[
        dict[str, str] | None,
        Field(description="Filter to runs with these key/value tags."),
    ] = None,
    created_after: Annotated[
        float | None,
        Field(description="Filter to runs created after this Unix timestamp."),
    ] = None,
    created_before: Annotated[
        float | None,
        Field(description="Filter to runs created before this Unix timestamp."),
    ] = None,
    updated_after: Annotated[
        float | None,
        Field(description="Filter to runs updated after this Unix timestamp."),
    ] = None,
    updated_before: Annotated[
        float | None,
        Field(description="Filter to runs updated before this Unix timestamp."),
    ] = None,
) -> str:
    """List recent Dagster+ runs. Filter by job name, run IDs, status, tags, or time range. Returns run IDs, job names, statuses, asset selections, re-execution lineage, and timestamps."""
    limit = min(limit, 100)
    filter_args: dict[str, Any] = {}
    if job_name:
        filter_args["pipelineName"] = job_name
    if run_ids:
        filter_args["runIds"] = run_ids
    if statuses:
        filter_args["statuses"] = statuses
    if tags:
        filter_args["tags"] = [{"key": k, "value": v} for k, v in tags.items()]
    if created_after:
        filter_args["createdAfter"] = created_after
    if created_before:
        filter_args["createdBefore"] = created_before
    if updated_after:
        filter_args["updatedAfter"] = updated_after
    if updated_before:
        filter_args["updatedBefore"] = updated_before
    data = gql(
        LIST_RUNS_QUERY,
        {
            "filter": filter_args or None,
            "cursor": cursor,
            "limit": limit,
        },
    )
    return json.dumps(data["runsOrError"], indent=2)


@server.tool()
def get_run(
    run_id: Annotated[
        str,
        Field(description="The run ID (UUID) to look up."),
    ],
) -> str:
    """Get full details for a single Dagster+ run by ID. Includes asset selection, re-execution lineage (parentRunId, rootRunId), step keys, step counts, and tags."""
    data = gql(RUN_BY_ID_QUERY, {"runId": run_id})
    return json.dumps(data["runOrError"], indent=2)


@server.tool()
def get_run_logs(
    run_id: Annotated[
        str,
        Field(description="The run ID to fetch logs for."),
    ],
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous get_run_logs call."),
    ] = None,
    limit: Annotated[
        int,
        Field(
            description=(
                "Max events to fetch per page (default 100, max 1000). "
                "When filter_types is set, filtering happens client-side "
                "after fetching — increase limit to see more matching events."
            ),
        ),
    ] = 100,
    filter_types: Annotated[
        list[str] | None,
        Field(
            description=(
                "Only return events of these __typename values, e.g. "
                "['ExecutionStepFailureEvent', 'RunFailureEvent']. "
                "Omit to return all event types."
            ),
        ),
    ] = None,
) -> str:
    """Get the structured event log for a Dagster+ run. Includes step start/success/failure events, log messages, asset materializations, engine errors, and resource init failures. Paginate with cursor if hasMore is true."""
    limit = min(limit, 1000)
    data = gql(
        RUN_LOGS_QUERY,
        {
            "runId": run_id,
            "afterCursor": cursor,
            "limit": limit,
        },
    )
    result = data["logsForRun"]
    if filter_types:
        filter_set = set(filter_types)
        if isinstance(result, dict) and "events" in result:
            result = {
                **result,
                "events": [
                    e for e in result["events"] if e.get("__typename") in filter_set
                ],
            }
    return json.dumps(result, indent=2)


@server.tool()
def get_run_compute_logs(
    log_key: Annotated[
        list[str],
        Field(
            description=(
                "The logKey array from a LogsCapturedEvent, e.g. "
                '["<run_id>", "compute_logs", "<step_key>"].'
            ),
        ),
    ],
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous call."),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Max bytes to return (default 50000)."),
    ] = 50000,
) -> str:
    """Get raw stdout and stderr compute logs for a step in a Dagster+ run. First use get_run_logs to find LogsCapturedEvent entries, which contain the logKey needed here. Returns both stdout and stderr as separate fields."""
    data = gql(
        COMPUTE_LOGS_QUERY,
        {
            "logKey": log_key,
            "cursor": cursor,
            "limit": limit,
        },
    )
    return json.dumps(data["capturedLogs"], indent=2)


@server.tool()
def get_captured_logs_metadata(
    log_key: Annotated[
        list[str],
        Field(description="The logKey array from a LogsCapturedEvent."),
    ],
) -> str:
    """Get signed download URLs and storage locations for stdout/stderr compute logs. Use when logs are too large to stream via get_run_compute_logs. logKey comes from a LogsCapturedEvent."""
    data = gql(
        CAPTURED_LOGS_METADATA_QUERY,
        {"logKey": log_key},
    )
    return json.dumps(data["capturedLogsMetadata"], indent=2)


@server.tool()
def get_daemon_health() -> str:
    """Get the health status of all Dagster+ daemons (scheduler, sensor, run coordinator, etc.). Returns whether each daemon is healthy, its last heartbeat time, and any error messages."""
    data = gql(DAEMON_HEALTH_QUERY)
    return json.dumps(data["instance"]["daemonHealth"]["allDaemonStatuses"], indent=2)


@server.tool()
def list_code_locations() -> str:
    """List all code locations in the Dagster+ workspace and their load status. Shows which locations loaded successfully and which have errors (e.g. import failures after a deploy)."""
    data = gql(CODE_LOCATIONS_QUERY)
    return json.dumps(data["workspaceOrError"], indent=2)


@server.tool()
def list_stale_assets(
    category: Annotated[
        StalenessCategory | None,
        Field(description="Filter to a specific staleness category. Omit for all."),
    ] = None,
    group: Annotated[
        str | None,
        Field(description="Filter to assets in this group name."),
    ] = None,
) -> str:
    """List assets with a stale status in Dagster+. CODE = code version changed since last materialization (shown as 'unsynced' in the UI); DATA = upstream data updated; DEPENDENCIES = upstream dependency structure changed. Returns asset key, group, compute kind, owners, jobs, and stale causes."""
    data = gql(STALE_ASSETS_QUERY)
    nodes = data["assetNodes"]
    stale = [n for n in nodes if n.get("staleStatus") == "STALE"]
    if group:
        stale = [n for n in stale if n.get("groupName") == group]
    if category:
        stale = [
            n
            for n in stale
            if any(c.get("category") == category for c in n.get("staleCauses", []))
        ]
    return json.dumps(stale, indent=2)


@server.tool()
def get_asset_materializations(
    asset_key: Annotated[
        str,
        Field(
            description="Asset key as slash-separated string, e.g. 'school/source/table'."
        ),
    ],
    limit: Annotated[
        int,
        Field(
            description="Number of materializations to return (default 10, max 100)."
        ),
    ] = 10,
    partition: Annotated[
        str | None,
        Field(description="Filter to a specific partition key."),
    ] = None,
) -> str:
    """Get recent materialization history for an asset. Returns timestamps, run IDs, partition keys, and metadata entries for each materialization."""
    asset_key_path = asset_key.split("/")
    limit = min(limit, 100)
    data = gql(
        ASSET_MATERIALIZATIONS_QUERY,
        {
            "assetKey": {"path": asset_key_path},
            "limit": limit,
            "partitions": [partition] if partition else None,
        },
    )
    nodes = data["assetNodes"]
    result = (
        nodes[0]
        if nodes
        else {"assetKey": {"path": asset_key_path}, "assetMaterializations": []}
    )
    return json.dumps(result, indent=2)


@server.tool()
def get_asset_partition_statuses(
    asset_key: Annotated[
        str,
        Field(description="Asset key as slash-separated string."),
    ],
) -> str:
    """Get partition materialization status for a partitioned asset. Returns aggregate counts (materialized, failed, missing) and, for time-partitioned assets, a range breakdown."""
    asset_key_path = asset_key.split("/")
    data = gql(
        ASSET_PARTITION_STATUSES_QUERY,
        {"assetKey": {"path": asset_key_path}},
    )
    nodes = data["assetNodes"]
    result = nodes[0] if nodes else {}
    return json.dumps(result, indent=2)


@server.tool()
def get_asset_check_executions(
    asset_key: Annotated[
        str,
        Field(description="Asset key as slash-separated string."),
    ],
    check_name: Annotated[
        str,
        Field(description="Name of the asset check."),
    ],
    limit: Annotated[
        int,
        Field(description="Number of executions to return (default 10, max 50)."),
    ] = 10,
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous call."),
    ] = None,
) -> str:
    """Get execution history for a specific asset check. Returns pass/fail status, severity, description, and metadata for each execution."""
    asset_key_path = asset_key.split("/")
    limit = min(limit, 50)
    data = gql(
        ASSET_CHECK_EXECUTIONS_QUERY,
        {
            "assetKey": {"path": asset_key_path},
            "checkName": check_name,
            "limit": limit,
            "cursor": cursor,
        },
    )
    return json.dumps(data["assetCheckExecutions"], indent=2)


@server.tool()
def get_asset_condition_evaluations(
    asset_key: Annotated[
        str,
        Field(description="Asset key as slash-separated string."),
    ],
    limit: Annotated[
        int,
        Field(
            description="Number of evaluation records to return (default 10, max 50)."
        ),
    ] = 10,
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous call."),
    ] = None,
) -> str:
    """Get automation condition evaluation history for an asset. Shows why the daemon requested or skipped each materialization — includes the full condition node tree with each node's label, operator type, and true/candidate counts."""
    asset_key_path = asset_key.split("/")
    limit = min(limit, 50)
    data = gql(
        ASSET_CONDITION_EVALUATIONS_QUERY,
        {
            "assetKey": {"path": asset_key_path},
            "limit": limit,
            "cursor": cursor,
        },
    )
    return json.dumps(data["assetConditionEvaluationRecordsOrError"], indent=2)


@server.tool()
def get_tick_history(
    name: Annotated[
        str,
        Field(description="The schedule or sensor name."),
    ],
    repository_location_name: Annotated[
        str,
        Field(description="The code location name (e.g. 'kipptaf')."),
    ],
    repository_name: Annotated[
        str,
        Field(
            description="The repository name within the code location (default '__repository__')."
        ),
    ] = "__repository__",
    limit: Annotated[
        int,
        Field(description="Number of ticks to return (default 20)."),
    ] = 20,
    statuses: Annotated[
        list[TickStatus] | None,
        Field(description="Filter to ticks with these statuses. Omit for all."),
    ] = None,
) -> str:
    """Get tick history for a schedule or sensor. Shows each evaluation tick with its status (SUCCESS, FAILURE, SKIPPED), run IDs launched, skip reason, and error details. Essential for diagnosing why a schedule or sensor is not firing."""
    data = gql(
        TICK_HISTORY_QUERY,
        {
            "name": name,
            "repositoryLocationName": repository_location_name,
            "repositoryName": repository_name,
            "limit": limit,
            "statuses": statuses or None,
        },
    )
    return json.dumps(data["instigationStateOrError"], indent=2)


@server.tool()
def list_backfills(
    status: Annotated[
        BackfillStatus | None,
        Field(description="Filter to backfills with this status."),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Number of backfills to return (default 20, max 100)."),
    ] = 20,
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous call."),
    ] = None,
) -> str:
    """List backfills in the Dagster+ deployment. Returns backfill ID, status, asset selection, partition counts by run status, and any errors."""
    limit = min(limit, 100)
    data = gql(
        BACKFILLS_QUERY,
        {
            "status": status,
            "cursor": cursor,
            "limit": limit,
        },
    )
    return json.dumps(data["partitionBackfillsOrError"], indent=2)


@server.tool()
def get_backfill(
    backfill_id: Annotated[
        str,
        Field(description="The backfill ID to look up."),
    ],
) -> str:
    """Get details for a single backfill by ID. Returns asset selection, partition names, status counts, error, and metadata."""
    data = gql(BACKFILL_QUERY, {"backfillId": backfill_id})
    return json.dumps(data["partitionBackfillOrError"], indent=2)


@server.tool()
def launch_run(
    asset_keys: Annotated[
        list[str],
        Field(
            description=(
                "Asset keys to materialize, as slash-separated strings "
                "(e.g. ['school/source/table'])."
            ),
        ),
    ],
    repository_location_name: Annotated[
        str,
        Field(description="The code location name (e.g. 'kipptaf')."),
    ],
    repository_name: Annotated[
        str,
        Field(description="The repository name (default '__repository__')."),
    ] = "__repository__",
    tags: Annotated[
        dict[str, str] | None,
        Field(description="Optional key/value tags for the run."),
    ] = None,
    run_config: Annotated[
        dict[str, Any] | None,
        Field(description="Optional run config overrides."),
    ] = None,
    confirm: Annotated[
        bool,
        Field(
            description=(
                "False (default) returns a preview of what would be launched. "
                "True executes the mutation."
            ),
        ),
    ] = False,
) -> str:
    """Launch a Dagster+ run to materialize selected assets. Call with confirm=False first to preview, then confirm=True to execute."""
    if not asset_keys:
        return json.dumps({"error": "asset_keys must not be empty"}, indent=2)
    params = _build_execution_params(
        asset_keys=asset_keys,
        repository_location_name=repository_location_name,
        repository_name=repository_name,
        tags=tags,
        run_config=run_config,
    )
    if not confirm:
        return json.dumps(
            {
                "mode": "preview",
                "execution_params": params,
                "action_required": "Call again with confirm=True to execute.",
            },
            indent=2,
        )
    data = gql(LAUNCH_RUN_MUTATION, {"executionParams": params})
    return json.dumps(data["launchRun"], indent=2)


@server.tool()
def launch_multiple_runs(
    runs: Annotated[
        list[dict[str, Any]],
        Field(
            description=(
                "List of run specs. Each dict must have 'asset_keys' (list of "
                "slash-separated strings) and 'repository_location_name' (str). "
                "Optional: 'repository_name' (str, default '__repository__'), "
                "'tags' (dict[str, str]), 'run_config' (dict)."
            ),
        ),
    ],
    confirm: Annotated[
        bool,
        Field(
            description=(
                "False (default) returns a preview of what would be launched. "
                "True executes the mutation."
            ),
        ),
    ] = False,
) -> str:
    """Launch multiple Dagster+ runs in a single batch. Call with confirm=False first to preview, then confirm=True to execute."""
    if not runs:
        return json.dumps({"error": "runs must not be empty"}, indent=2)
    for i, r in enumerate(runs):
        for key in ("asset_keys", "repository_location_name"):
            if key not in r:
                return json.dumps(
                    {"error": f"runs[{i}] missing required key '{key}'"},
                    indent=2,
                )
        if not r["asset_keys"]:
            return json.dumps(
                {"error": f"runs[{i}] asset_keys must not be empty"},
                indent=2,
            )
    params_list = [
        _build_execution_params(
            asset_keys=r["asset_keys"],
            repository_location_name=r["repository_location_name"],
            repository_name=r.get("repository_name", "__repository__"),
            tags=r.get("tags"),
            run_config=r.get("run_config"),
        )
        for r in runs
    ]
    if not confirm:
        return json.dumps(
            {
                "mode": "preview",
                "runs": params_list,
                "action_required": "Call again with confirm=True to execute.",
            },
            indent=2,
        )
    data = gql(
        LAUNCH_MULTIPLE_RUNS_MUTATION,
        {"executionParamsList": params_list},
    )
    return json.dumps(data["launchMultipleRuns"], indent=2)


@server.tool()
def reexecute_run(
    parent_run_id: Annotated[
        str,
        Field(description="The run ID (UUID) of the failed run to re-execute."),
    ],
    strategy: Annotated[
        ReexecutionStrategy,
        Field(
            description=(
                "Re-execution strategy: FROM_FAILURE (retry from failed step), "
                "FROM_ASSET_FAILURE (retry from failed asset), or "
                "ALL_STEPS (re-run everything)."
            ),
        ),
    ],
    extra_tags: Annotated[
        dict[str, str] | None,
        Field(description="Optional additional tags for the new run."),
    ] = None,
    confirm: Annotated[
        bool,
        Field(
            description=(
                "False (default) fetches the parent run from Dagster+ and "
                "returns a preview with its details. True executes the mutation."
            ),
        ),
    ] = False,
) -> str:
    """Re-execute a previous Dagster+ run with the given strategy. Call with confirm=False first to preview parent run details, then confirm=True to execute."""
    if not confirm:
        parent_data = gql(RUN_BY_ID_QUERY, {"runId": parent_run_id})
        return json.dumps(
            {
                "mode": "preview",
                "parent_run": parent_data["runOrError"],
                "strategy": strategy,
                "extra_tags": extra_tags,
                "action_required": "Call again with confirm=True to execute.",
            },
            indent=2,
        )
    reexecution_params: dict[str, Any] = {
        "parentRunId": parent_run_id,
        "strategy": strategy,
    }
    if extra_tags:
        reexecution_params["extraTags"] = [
            {"key": k, "value": v} for k, v in extra_tags.items()
        ]
    data = gql(
        LAUNCH_RUN_REEXECUTION_MUTATION,
        {"reexecutionParams": reexecution_params},
    )
    return json.dumps(data["launchRunReexecution"], indent=2)
