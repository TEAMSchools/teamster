"""FastMCP server instance and GraphQL client for Dagster+."""

import os
from typing import Any

import httpx

from mcp.server.fastmcp import FastMCP

DAGSTER_CLOUD_API_TOKEN = os.environ["DAGSTER_CLOUD_API_TOKEN"]
DAGSTER_CLOUD_ORGANIZATION_ID = os.environ.get(
    "DAGSTER_CLOUD_ORGANIZATION_ID", "kipptaf"
)
DAGSTER_CLOUD_DEPLOYMENT = os.environ.get("DAGSTER_CLOUD_DEPLOYMENT", "prod")

GRAPHQL_URL = (
    f"https://{DAGSTER_CLOUD_ORGANIZATION_ID}.dagster.cloud"
    f"/{DAGSTER_CLOUD_DEPLOYMENT}/graphql"
)

server = FastMCP(
    "dagster-plus",
    instructions=(
        "Dagster+ operational server for KIPP TEAM & Family Schools. "
        "To diagnose asset issues: use search_assets to discover assets by "
        "prefix, then get_asset_health for health status (HEALTHY, DEGRADED, "
        "WARNING, UNKNOWN) and get_asset_staleness for staleness root causes. "
        "Avoid list_stale_assets — it fetches the entire asset graph and can "
        "be very large. Mutation tools (launch_run, launch_multiple_runs, "
        "reexecute_run) require confirm=True to execute — always preview first "
        "with confirm=False."
    ),
)

_client = httpx.AsyncClient(
    base_url=GRAPHQL_URL,
    headers={
        "Dagster-Cloud-Api-Token": DAGSTER_CLOUD_API_TOKEN,
        "Content-Type": "application/json",
    },
    timeout=60,
)


class GraphQLError(Exception):
    """Structured error from the Dagster+ GraphQL API."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message)
        self.message = message
        self.details = details


async def gql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query against the Dagster+ API."""
    response = await _client.post(
        "", json={"query": query, "variables": variables or {}}
    )
    if not response.is_success:
        raise GraphQLError(
            f"Dagster API returned {response.status_code}",
            details=response.text[:500],
        )
    data = response.json()
    if "errors" in data:
        raise GraphQLError("GraphQL query failed", details=data["errors"])
    return data["data"]
