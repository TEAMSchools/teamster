"""MCP server for Dagster+ run logs and daemon diagnostics.

Exposes tools for reading run event logs, compute logs (stdout/stderr),
and daemon health from a Dagster+ deployment via its GraphQL API.

Requires the following environment variables:
- DAGSTER_CLOUD_API_TOKEN: A Dagster+ user token or agent token
- DAGSTER_CLOUD_ORGANIZATION_ID: The org slug (e.g. "teamschools")
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
    "DAGSTER_CLOUD_ORGANIZATION_ID", "teamschools"
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
      }
      cursor
      hasMore
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

COMPUTE_LOGS_QUERY = """
query GetComputeLogs($logKey: [String!]!, $ioType: ComputeIOType!, $cursor: String, $limit: Int) {
  capturedLogs(logKey: $logKey, cursor: $cursor, limit: $limit, ioType: $ioType) {
    data
    cursor
    downloadUrl
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
    staleStatus
    staleCauses {
      key { path }
      reason
      category
      dependency { path }
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
        numRequested
        numSkipped
        numDiscarded
        runIds
        evaluation {
          rootUniqueId
          evaluationNodes {
            uniqueId
            childUniqueIds
            ... on UnpartitionedAssetConditionEvaluationNode {
              description
              status
              startTimestamp
              endTimestamp
            }
            ... on PartitionedAssetConditionEvaluationNode {
              description
              numTrue
              startTimestamp
              endTimestamp
            }
            ... on SpecificPartitionAssetConditionEvaluationNode {
              description
              status
            }
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


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_runs",
            description=(
                "List recent Dagster+ runs. Optionally filter by job name, status, "
                "or tags. Returns run IDs, job names, statuses, and timestamps."
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
                        "description": "Filter to runs for this job/asset job name.",
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
                },
            },
        ),
        types.Tool(
            name="get_run",
            description="Get details for a single Dagster+ run by its run ID.",
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
                "and errors with stack traces. Paginate with cursor if hasMore is true."
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
                        "description": "Max events to return per page (default 100, max 1000).",
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
                "Get raw stdout or stderr compute logs for a step in a Dagster+ run. "
                "First use get_run_logs to find LogsCapturedEvent entries, which contain "
                "the logKey needed here."
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
                    "io_type": {
                        "type": "string",
                        "enum": ["STDOUT", "STDERR"],
                        "description": "Whether to fetch stdout or stderr.",
                        "default": "STDERR",
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
            name="list_stale_assets",
            description=(
                "List assets that have a stale (unsynced) status in Dagster+. "
                "CODE category means the asset's code version changed since last "
                "materialization (shown as 'unsynced' in the UI). DATA category means "
                "an upstream asset has been updated. Returns each stale asset's key, "
                "group, and the specific causes of staleness."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["CODE", "DATA"],
                        "description": (
                            "Filter to a specific staleness category. "
                            "CODE = unsynced (code version changed); "
                            "DATA = upstream data updated. Omit to return all stale assets."
                        ),
                    },
                    "group": {
                        "type": "string",
                        "description": "Filter to assets in this group name.",
                    },
                },
            },
        ),
        types.Tool(
            name="get_asset_condition_evaluations",
            description=(
                "Get automation condition evaluation history for an asset. "
                "Shows why the daemon requested or skipped each materialization — "
                "includes per-tick counts (requested/skipped/discarded) and the full "
                "condition tree so you can see which sub-condition passed or failed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "asset_key": {
                        "type": "string",
                        "description": (
                            "The asset key as a slash-separated string, "
                            'e.g. "my_group/my_asset" or "schema/table".'
                        ),
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
            name="get_daemon_health",
            description=(
                "Get the health status of all Dagster+ daemons (scheduler, sensor, "
                "run coordinator, etc.). Returns whether each daemon is healthy, "
                "its last heartbeat time, and any error messages."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    try:
        if name == "list_runs":
            limit = min(arguments.get("limit", 20), 100)
            filter_args: dict[str, Any] = {}
            if job_name := arguments.get("job_name"):
                filter_args["pipelineName"] = job_name
            if statuses := arguments.get("statuses"):
                filter_args["statuses"] = statuses
            if tags := arguments.get("tags"):
                filter_args["tags"] = [
                    {"key": k, "value": v} for k, v in tags.items()
                ]
            data = gql(
                LIST_RUNS_QUERY,
                {
                    "filter": filter_args or None,
                    "cursor": arguments.get("cursor"),
                    "limit": limit,
                },
            )
            result = data["runsOrError"]
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

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
                    "ioType": arguments.get("io_type", "STDERR"),
                    "cursor": arguments.get("cursor"),
                    "limit": arguments.get("limit", 50000),
                },
            )
            return [
                types.TextContent(
                    type="text", text=json.dumps(data["capturedLogs"], indent=2)
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
                    n for n in stale
                    if any(c.get("category") == category for c in n.get("staleCauses", []))
                ]
            return [types.TextContent(type="text", text=json.dumps(stale, indent=2))]

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
