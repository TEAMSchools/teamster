"""MCP server for Dagster+ operational diagnostics.

Exposes tools for querying runs, logs, assets, automation conditions,
schedules, sensors, backfills, and code locations from a Dagster+
deployment via its GraphQL API.

Requires the following environment variables:
- DAGSTER_CLOUD_API_TOKEN: A Dagster+ user token or agent token
- DAGSTER_CLOUD_ORGANIZATION_ID: The org slug (e.g. "kipptaf")
- DAGSTER_CLOUD_DEPLOYMENT: The deployment name (default: "prod")
"""

import json
import os
from typing import Any

import httpx

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

DAGSTER_CLOUD_API_TOKEN = os.environ.get("DAGSTER_CLOUD_API_TOKEN", "")
DAGSTER_CLOUD_ORGANIZATION_ID = os.environ.get(
    "DAGSTER_CLOUD_ORGANIZATION_ID", "kipptaf"
)
DAGSTER_CLOUD_DEPLOYMENT = os.environ.get("DAGSTER_CLOUD_DEPLOYMENT", "prod")

GRAPHQL_URL = (
    f"https://{DAGSTER_CLOUD_ORGANIZATION_ID}.dagster.cloud"
    f"/{DAGSTER_CLOUD_DEPLOYMENT}/graphql"
)

server = Server("dagster-plus")


def gql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query against the Dagster+ API."""
    with httpx.Client(timeout=30) as client:
        response = client.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables or {}},
            headers={
                "Dagster-Cloud-Api-Token": DAGSTER_CLOUD_API_TOKEN,
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data["data"]


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

LIST_RUNS_QUERY = """
query ListRuns($filter: RunsFilter, $cursor: String, $limit: Int) {
  runsOrError(filter: $filter, cursor: $cursor, limit: $limit) {
    ... on Runs {
      results {
        id
        jobName
        status
        creationTime
        startTime
        endTime
        updateTime
        parentRunId
        rootRunId
        assetSelection { path }
        tags { key value }
        repositoryOrigin {
          repositoryName
          repositoryLocationName
        }
      }
    }
    ... on InvalidPipelineRunsFilterError {
      message
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

RUN_BY_ID_QUERY = """
query GetRun($runId: ID!) {
  runOrError(runId: $runId) {
    ... on Run {
      id
      jobName
      status
      creationTime
      startTime
      endTime
      updateTime
      parentRunId
      rootRunId
      stepKeysToExecute
      assetSelection { path }
      tags { key value }
      stats {
        ... on RunStatsSnapshot {
          stepsSucceeded
          stepsFailed
          materializations
          expectations
        }
      }
      repositoryOrigin {
        repositoryName
        repositoryLocationName
      }
    }
    ... on RunNotFoundError {
      message
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

RUN_LOGS_QUERY = """
query GetRunLogs($runId: ID!, $afterCursor: String, $limit: Int) {
  logsForRun(runId: $runId, afterCursor: $afterCursor, limit: $limit) {
    ... on EventConnection {
      events {
        __typename
        timestamp
        ... on MessageEvent {
          message
          level
          stepKey
        }
        ... on ExecutionStepFailureEvent {
          stepKey
          error {
            message
            stack
            errorChain {
              error { message stack }
            }
          }
        }
        ... on RunFailureEvent {
          error {
            message
            stack
            errorChain {
              error { message stack }
            }
          }
        }
        ... on ExecutionStepStartEvent { stepKey }
        ... on ExecutionStepSuccessEvent { stepKey }
        ... on ExecutionStepSkippedEvent { stepKey }
        ... on ExecutionStepRestartEvent { stepKey }
        ... on ExecutionStepUpForRetryEvent {
          stepKey
          error { message stack }
        }
        ... on LogsCapturedEvent {
          logKey
          stepKeys
          externalUrl
        }
        ... on AssetMaterializationPlannedEvent {
          assetKey { path }
        }
        ... on MaterializationEvent {
          assetKey { path }
          label
          description
        }
        ... on EngineEvent {
          error { message stack }
        }
        ... on ResourceInitFailureEvent {
          stepKey
          error { message stack }
        }
      }
      cursor
      hasMore
    }
    ... on RunNotFoundError {
      message
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

COMPUTE_LOGS_QUERY = """
query GetComputeLogs($logKey: [String!]!, $cursor: String, $limit: Int) {
  capturedLogs(logKey: $logKey, cursor: $cursor, limit: $limit) {
    stdout
    stderr
    cursor
  }
}
"""

CAPTURED_LOGS_METADATA_QUERY = """
query GetCapturedLogsMetadata($logKey: [String!]!) {
  capturedLogsMetadata(logKey: $logKey) {
    stdoutDownloadUrl
    stdoutLocation
    stderrDownloadUrl
    stderrLocation
  }
}
"""

DAEMON_HEALTH_QUERY = """
query DaemonHealth {
  instance {
    daemonHealth {
      allDaemonStatuses {
        daemonType
        healthy
        id
        required
        lastHeartbeatTime
        lastHeartbeatErrors {
          message
          stack
          errorChain {
            error { message stack }
          }
        }
      }
    }
  }
}
"""

STALE_ASSETS_QUERY = """
query GetStaleAssets {
  assetNodes {
    assetKey { path }
    groupName
    description
    computeKind
    isPartitioned
    jobNames
    owners {
      ... on UserAssetOwner { email }
      ... on TeamAssetOwner { team }
    }
    changedReasons
    staleStatus
    staleCauses {
      key { path }
      partitionKey
      category
      reason
      dependency { path }
      dependencyPartitionKey
    }
  }
}
"""

ASSET_MATERIALIZATIONS_QUERY = """
query GetAssetMaterializations($assetKey: AssetKeyInput!, $limit: Int, $partitions: [String!]) {
  assetNodes(assetKeys: [$assetKey]) {
    assetKey { path }
    assetMaterializations(limit: $limit, partitions: $partitions) {
      timestamp
      runId
      partition
      stepKey
      tags { key value }
      metadataEntries {
        label
        description
        ... on TextMetadataEntry { text }
        ... on UrlMetadataEntry { url }
        ... on FloatMetadataEntry { floatValue }
        ... on IntMetadataEntry { intValue }
        ... on BoolMetadataEntry { boolValue }
        ... on PathMetadataEntry { path }
        ... on JsonMetadataEntry { jsonString }
        ... on MarkdownMetadataEntry { mdStr }
      }
    }
  }
}
"""

ASSET_PARTITION_STATUSES_QUERY = """
query GetAssetPartitionStatuses($assetKey: AssetKeyInput!) {
  assetNodes(assetKeys: [$assetKey]) {
    assetKey { path }
    isPartitioned
    partitionStats {
      numMaterialized
      numMaterializing
      numPartitions
      numFailed
    }
    assetPartitionStatuses {
      ... on TimePartitionStatuses {
        ranges {
          status
          startKey
          endKey
          startTime
          endTime
        }
      }
      ... on DefaultPartitionStatuses {
        materializedPartitions
        failedPartitions
        unmaterializedPartitions
        materializingPartitions
      }
    }
  }
}
"""

ASSET_CHECK_EXECUTIONS_QUERY = """
query GetAssetCheckExecutions($assetKey: AssetKeyInput!, $checkName: String!, $limit: Int!, $cursor: String) {
  assetCheckExecutions(assetKey: $assetKey, checkName: $checkName, limit: $limit, cursor: $cursor) {
    id
    runId
    status
    timestamp
    stepKey
    partition
    evaluation {
      success
      severity
      description
      targetMaterialization {
        timestamp
        runId
        storageId
      }
      metadataEntries {
        label
        description
        ... on TextMetadataEntry { text }
        ... on UrlMetadataEntry { url }
        ... on FloatMetadataEntry { floatValue }
        ... on IntMetadataEntry { intValue }
        ... on BoolMetadataEntry { boolValue }
        ... on JsonMetadataEntry { jsonString }
      }
    }
  }
}
"""

ASSET_CONDITION_EVALUATIONS_QUERY = """
query GetAssetConditionEvaluations($assetKey: AssetKeyInput!, $limit: Int!, $cursor: String) {
  assetConditionEvaluationRecordsOrError(assetKey: $assetKey, limit: $limit, cursor: $cursor) {
    ... on AssetConditionEvaluationRecords {
      records {
        evaluationId
        timestamp
        startTimestamp
        endTimestamp
        numRequested
        runIds
        rootUniqueId
        isLegacy
        assetKey { path }
        evaluationNodes {
          uniqueId
          userLabel
          expandedLabel
          startTimestamp
          endTimestamp
          numTrue
          numCandidates
          isPartitioned
          childUniqueIds
          operatorType
          sinceMetadata {
            triggerEvaluationId
            triggerTimestamp
            resetEvaluationId
            resetTimestamp
          }
        }
      }
    }
    ... on AutoMaterializeAssetEvaluationNeedsMigrationError {
      message
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

TICK_HISTORY_QUERY = """
query GetTickHistory(
  $name: String!
  $repositoryName: String!
  $repositoryLocationName: String!
  $limit: Int
  $statuses: [InstigationTickStatus!]
) {
  instigationStateOrError(instigationSelector: {
    name: $name
    repositoryName: $repositoryName
    repositoryLocationName: $repositoryLocationName
  }) {
    ... on InstigationState {
      name
      instigationType
      status
      ticks(limit: $limit, statuses: $statuses) {
        id
        tickId
        status
        timestamp
        endTimestamp
        runIds
        skipReason
        requestedAssetKeys { path }
        requestedAssetMaterializationCount
        error {
          message
          stack
          errorChain { error { message stack } }
        }
      }
    }
    ... on InstigationStateNotFoundError {
      name
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

CODE_LOCATIONS_QUERY = """
query ListCodeLocations {
  workspaceOrError {
    ... on Workspace {
      locationEntries {
        id
        name
        loadStatus
        updatedTimestamp
        locationOrLoadError {
          ... on RepositoryLocation {
            id
            name
            repositories {
              name
            }
          }
          ... on PythonError {
            message
            stack
          }
        }
      }
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

BACKFILLS_QUERY = """
query ListBackfills($status: BulkActionStatus, $cursor: String, $limit: Int) {
  partitionBackfillsOrError(status: $status, cursor: $cursor, limit: $limit) {
    ... on PartitionBackfills {
      results {
        id
        status
        timestamp
        endTimestamp
        numPartitions
        isAssetBackfill
        assetSelection { path }
        partitionStatusCounts { runStatus count }
        error { message stack }
        user
        tags { key value }
        title
        hasCancelPermission
        hasResumePermission
      }
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

BACKFILL_QUERY = """
query GetBackfill($backfillId: String!) {
  partitionBackfillOrError(backfillId: $backfillId) {
    ... on PartitionBackfill {
      id
      status
      timestamp
      endTimestamp
      numPartitions
      partitionNames
      isAssetBackfill
      assetSelection { path }
      partitionStatusCounts { runStatus count }
      error { message stack }
      user
      tags { key value }
      title
      description
      hasCancelPermission
      hasResumePermission
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_runs",
            description=(
                "List recent Dagster+ runs. Filter by job name, run IDs, status, "
                "tags, or time range. Returns run IDs, job names, statuses, asset "
                "selections, re-execution lineage, and timestamps."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max number of runs to return (default 20, max 100).",
                        "default": 20,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor from a previous list_runs call.",
                    },
                    "job_name": {
                        "type": "string",
                        "description": "Filter to runs for this job name.",
                    },
                    "run_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter to specific run IDs.",
                    },
                    "statuses": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "QUEUED",
                                "NOT_STARTED",
                                "MANAGED",
                                "STARTING",
                                "STARTED",
                                "SUCCESS",
                                "FAILURE",
                                "CANCELING",
                                "CANCELED",
                            ],
                        },
                        "description": "Filter to runs with these statuses.",
                    },
                    "tags": {
                        "type": "object",
                        "description": "Filter to runs with these key/value tags.",
                        "additionalProperties": {"type": "string"},
                    },
                    "created_after": {
                        "type": "number",
                        "description": "Filter to runs created after this Unix timestamp.",
                    },
                    "created_before": {
                        "type": "number",
                        "description": "Filter to runs created before this Unix timestamp.",
                    },
                    "updated_after": {
                        "type": "number",
                        "description": "Filter to runs updated after this Unix timestamp.",
                    },
                    "updated_before": {
                        "type": "number",
                        "description": "Filter to runs updated before this Unix timestamp.",
                    },
                },
            },
        ),
        types.Tool(
            name="get_run",
            description=(
                "Get full details for a single Dagster+ run by ID. Includes asset "
                "selection, re-execution lineage (parentRunId, rootRunId), step keys, "
                "step counts, and tags."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "The run ID (UUID) to look up.",
                    }
                },
                "required": ["run_id"],
            },
        ),
        types.Tool(
            name="get_run_logs",
            description=(
                "Get the structured event log for a Dagster+ run. Includes step "
                "start/success/failure events, log messages, asset materializations, "
                "engine errors, and resource init failures. Paginate with cursor if "
                "hasMore is true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "The run ID to fetch logs for.",
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor from a previous get_run_logs call.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Max events to fetch per page (default 100, max 1000). "
                            "When filter_types is set, filtering happens client-side "
                            "after fetching — increase limit to see more matching events."
                        ),
                        "default": 100,
                    },
                    "filter_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Only return events of these __typename values, e.g. "
                            "['ExecutionStepFailureEvent', 'RunFailureEvent']. "
                            "Omit to return all event types."
                        ),
                    },
                },
                "required": ["run_id"],
            },
        ),
        types.Tool(
            name="get_run_compute_logs",
            description=(
                "Get raw stdout and stderr compute logs for a step in a Dagster+ run. "
                "First use get_run_logs to find LogsCapturedEvent entries, which contain "
                "the logKey needed here. Returns both stdout and stderr as separate fields."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "log_key": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "The logKey array from a LogsCapturedEvent, e.g. "
                            '["<run_id>", "compute_logs", "<step_key>"].'
                        ),
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor from a previous call.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max bytes to return (default 50000).",
                        "default": 50000,
                    },
                },
                "required": ["log_key"],
            },
        ),
        types.Tool(
            name="get_captured_logs_metadata",
            description=(
                "Get signed download URLs and storage locations for stdout/stderr "
                "compute logs. Use when logs are too large to stream via "
                "get_run_compute_logs. logKey comes from a LogsCapturedEvent."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "log_key": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The logKey array from a LogsCapturedEvent.",
                    },
                },
                "required": ["log_key"],
            },
        ),
        types.Tool(
            name="get_daemon_health",
            description=(
                "Get the health status of all Dagster+ daemons (scheduler, sensor, "
                "run coordinator, etc.). Returns whether each daemon is healthy, "
                "its last heartbeat time, and any error messages."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="list_code_locations",
            description=(
                "List all code locations in the Dagster+ workspace and their load "
                "status. Shows which locations loaded successfully and which have "
                "errors (e.g. import failures after a deploy)."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="list_stale_assets",
            description=(
                "List assets with a stale status in Dagster+. "
                "CODE = code version changed since last materialization (shown as "
                "'unsynced' in the UI); DATA = upstream data updated; "
                "DEPENDENCIES = upstream dependency structure changed. "
                "Returns asset key, group, compute kind, owners, jobs, and stale causes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["CODE", "DATA", "DEPENDENCIES"],
                        "description": "Filter to a specific staleness category. Omit for all.",
                    },
                    "group": {
                        "type": "string",
                        "description": "Filter to assets in this group name.",
                    },
                },
            },
        ),
        types.Tool(
            name="get_asset_materializations",
            description=(
                "Get recent materialization history for an asset. Returns timestamps, "
                "run IDs, partition keys, and metadata entries for each materialization."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "asset_key": {
                        "type": "string",
                        "description": "Asset key as slash-separated string, e.g. 'school/source/table'.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of materializations to return (default 10, max 100).",
                        "default": 10,
                    },
                    "partition": {
                        "type": "string",
                        "description": "Filter to a specific partition key.",
                    },
                },
                "required": ["asset_key"],
            },
        ),
        types.Tool(
            name="get_asset_partition_statuses",
            description=(
                "Get partition materialization status for a partitioned asset. "
                "Returns aggregate counts (materialized, failed, missing) and, for "
                "time-partitioned assets, a range breakdown."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "asset_key": {
                        "type": "string",
                        "description": "Asset key as slash-separated string.",
                    },
                },
                "required": ["asset_key"],
            },
        ),
        types.Tool(
            name="get_asset_check_executions",
            description=(
                "Get execution history for a specific asset check. Returns pass/fail "
                "status, severity, description, and metadata for each execution."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "asset_key": {
                        "type": "string",
                        "description": "Asset key as slash-separated string.",
                    },
                    "check_name": {
                        "type": "string",
                        "description": "Name of the asset check.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of executions to return (default 10, max 50).",
                        "default": 10,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor from a previous call.",
                    },
                },
                "required": ["asset_key", "check_name"],
            },
        ),
        types.Tool(
            name="get_asset_condition_evaluations",
            description=(
                "Get automation condition evaluation history for an asset. Shows why "
                "the daemon requested or skipped each materialization — includes the "
                "full condition node tree with each node's label, operator type, and "
                "true/candidate counts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "asset_key": {
                        "type": "string",
                        "description": "Asset key as slash-separated string.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of evaluation records to return (default 10, max 50).",
                        "default": 10,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor from a previous call.",
                    },
                },
                "required": ["asset_key"],
            },
        ),
        types.Tool(
            name="get_tick_history",
            description=(
                "Get tick history for a schedule or sensor. Shows each evaluation tick "
                "with its status (SUCCESS, FAILURE, SKIPPED), run IDs launched, skip "
                "reason, and error details. Essential for diagnosing why a schedule or "
                "sensor is not firing."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The schedule or sensor name.",
                    },
                    "repository_location_name": {
                        "type": "string",
                        "description": "The code location name (e.g. 'kipptaf').",
                    },
                    "repository_name": {
                        "type": "string",
                        "description": "The repository name within the code location (default '__repository__').",
                        "default": "__repository__",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of ticks to return (default 20).",
                        "default": 20,
                    },
                    "statuses": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["SUCCESS", "FAILURE", "SKIPPED", "STARTED"],
                        },
                        "description": "Filter to ticks with these statuses. Omit for all.",
                    },
                },
                "required": ["name", "repository_location_name"],
            },
        ),
        types.Tool(
            name="list_backfills",
            description=(
                "List backfills in the Dagster+ deployment. Returns backfill ID, "
                "status, asset selection, partition counts by run status, and "
                "any errors."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": [
                            "REQUESTED",
                            "CANCELING",
                            "CANCELED",
                            "FAILED",
                            "COMPLETED",
                        ],
                        "description": "Filter to backfills with this status.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of backfills to return (default 20, max 100).",
                        "default": 20,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor from a previous call.",
                    },
                },
            },
        ),
        types.Tool(
            name="get_backfill",
            description=(
                "Get details for a single backfill by ID. Returns asset selection, "
                "partition names, status counts, error, and metadata."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "backfill_id": {
                        "type": "string",
                        "description": "The backfill ID to look up.",
                    },
                },
                "required": ["backfill_id"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        if name == "list_runs":
            limit = min(arguments.get("limit", 20), 100)
            filter_args: dict[str, Any] = {}
            if job_name := arguments.get("job_name"):
                filter_args["pipelineName"] = job_name
            if run_ids := arguments.get("run_ids"):
                filter_args["runIds"] = run_ids
            if statuses := arguments.get("statuses"):
                filter_args["statuses"] = statuses
            if tags := arguments.get("tags"):
                filter_args["tags"] = [{"key": k, "value": v} for k, v in tags.items()]
            if created_after := arguments.get("created_after"):
                filter_args["createdAfter"] = created_after
            if created_before := arguments.get("created_before"):
                filter_args["createdBefore"] = created_before
            if updated_after := arguments.get("updated_after"):
                filter_args["updatedAfter"] = updated_after
            if updated_before := arguments.get("updated_before"):
                filter_args["updatedBefore"] = updated_before
            data = gql(
                LIST_RUNS_QUERY,
                {
                    "filter": filter_args or None,
                    "cursor": arguments.get("cursor"),
                    "limit": limit,
                },
            )
            return [
                types.TextContent(
                    type="text", text=json.dumps(data["runsOrError"], indent=2)
                )
            ]

        elif name == "get_run":
            data = gql(RUN_BY_ID_QUERY, {"runId": arguments["run_id"]})
            return [
                types.TextContent(
                    type="text", text=json.dumps(data["runOrError"], indent=2)
                )
            ]

        elif name == "get_run_logs":
            limit = min(arguments.get("limit", 100), 1000)
            data = gql(
                RUN_LOGS_QUERY,
                {
                    "runId": arguments["run_id"],
                    "afterCursor": arguments.get("cursor"),
                    "limit": limit,
                },
            )
            result = data["logsForRun"]
            if filter_types := arguments.get("filter_types"):
                filter_set = set(filter_types)
                if isinstance(result, dict) and "events" in result:
                    result = {
                        **result,
                        "events": [
                            e
                            for e in result["events"]
                            if e.get("__typename") in filter_set
                        ],
                    }
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_run_compute_logs":
            data = gql(
                COMPUTE_LOGS_QUERY,
                {
                    "logKey": arguments["log_key"],
                    "cursor": arguments.get("cursor"),
                    "limit": arguments.get("limit", 50000),
                },
            )
            return [
                types.TextContent(
                    type="text", text=json.dumps(data["capturedLogs"], indent=2)
                )
            ]

        elif name == "get_captured_logs_metadata":
            data = gql(
                CAPTURED_LOGS_METADATA_QUERY,
                {"logKey": arguments["log_key"]},
            )
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(data["capturedLogsMetadata"], indent=2),
                )
            ]

        elif name == "get_daemon_health":
            data = gql(DAEMON_HEALTH_QUERY)
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        data["instance"]["daemonHealth"]["allDaemonStatuses"], indent=2
                    ),
                )
            ]

        elif name == "list_code_locations":
            data = gql(CODE_LOCATIONS_QUERY)
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(data["workspaceOrError"], indent=2),
                )
            ]

        elif name == "list_stale_assets":
            data = gql(STALE_ASSETS_QUERY)
            nodes = data["assetNodes"]
            stale = [n for n in nodes if n.get("staleStatus") == "STALE"]
            if group := arguments.get("group"):
                stale = [n for n in stale if n.get("groupName") == group]
            if category := arguments.get("category"):
                stale = [
                    n
                    for n in stale
                    if any(
                        c.get("category") == category for c in n.get("staleCauses", [])
                    )
                ]
            return [types.TextContent(type="text", text=json.dumps(stale, indent=2))]

        elif name == "get_asset_materializations":
            asset_key_path = arguments["asset_key"].split("/")
            limit = min(arguments.get("limit", 10), 100)
            partition = arguments.get("partition")
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
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_asset_partition_statuses":
            asset_key_path = arguments["asset_key"].split("/")
            data = gql(
                ASSET_PARTITION_STATUSES_QUERY,
                {"assetKey": {"path": asset_key_path}},
            )
            nodes = data["assetNodes"]
            result = nodes[0] if nodes else {}
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_asset_check_executions":
            asset_key_path = arguments["asset_key"].split("/")
            limit = min(arguments.get("limit", 10), 50)
            data = gql(
                ASSET_CHECK_EXECUTIONS_QUERY,
                {
                    "assetKey": {"path": asset_key_path},
                    "checkName": arguments["check_name"],
                    "limit": limit,
                    "cursor": arguments.get("cursor"),
                },
            )
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(data["assetCheckExecutions"], indent=2),
                )
            ]

        elif name == "get_asset_condition_evaluations":
            asset_key_path = arguments["asset_key"].split("/")
            limit = min(arguments.get("limit", 10), 50)
            data = gql(
                ASSET_CONDITION_EVALUATIONS_QUERY,
                {
                    "assetKey": {"path": asset_key_path},
                    "limit": limit,
                    "cursor": arguments.get("cursor"),
                },
            )
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        data["assetConditionEvaluationRecordsOrError"], indent=2
                    ),
                )
            ]

        elif name == "get_tick_history":
            data = gql(
                TICK_HISTORY_QUERY,
                {
                    "name": arguments["name"],
                    "repositoryLocationName": arguments["repository_location_name"],
                    "repositoryName": arguments.get(
                        "repository_name", "__repository__"
                    ),
                    "limit": arguments.get("limit", 20),
                    "statuses": arguments.get("statuses") or None,
                },
            )
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(data["instigationStateOrError"], indent=2),
                )
            ]

        elif name == "list_backfills":
            limit = min(arguments.get("limit", 20), 100)
            data = gql(
                BACKFILLS_QUERY,
                {
                    "status": arguments.get("status"),
                    "cursor": arguments.get("cursor"),
                    "limit": limit,
                },
            )
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(data["partitionBackfillsOrError"], indent=2),
                )
            ]

        elif name == "get_backfill":
            data = gql(BACKFILL_QUERY, {"backfillId": arguments["backfill_id"]})
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(data["partitionBackfillOrError"], indent=2),
                )
            ]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {e}")]


async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
