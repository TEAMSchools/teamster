"""FastMCP server instance and GraphQL client for Dagster+."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from mcp.server.fastmcp import FastMCP

logging.getLogger("httpx").setLevel(logging.WARNING)

DAGSTER_CLOUD_API_TOKEN = os.environ["DAGSTER_CLOUD_API_TOKEN"]
DAGSTER_CLOUD_ORGANIZATION_ID = os.environ.get(
    "DAGSTER_CLOUD_ORGANIZATION_ID", "kipptaf"
)
DAGSTER_CLOUD_DEPLOYMENT = os.environ.get("DAGSTER_CLOUD_DEPLOYMENT", "prod")

GRAPHQL_URL = (
    f"https://{DAGSTER_CLOUD_ORGANIZATION_ID}.dagster.cloud"
    f"/{DAGSTER_CLOUD_DEPLOYMENT}/graphql"
)

_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    global _client  # noqa: PLW0603
    _client = httpx.AsyncClient(
        base_url=GRAPHQL_URL,
        headers={
            "Dagster-Cloud-Api-Token": DAGSTER_CLOUD_API_TOKEN,
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    try:
        yield
    finally:
        await _client.aclose()
        _client = None


server = FastMCP(
    "dagster-plus",
    instructions=(
        "Dagster+ operational server for KIPP TEAM & Family Schools. "
        "To diagnose asset issues: use search_assets to discover assets by "
        "prefix, then get_asset_health for health status (HEALTHY, DEGRADED, "
        "WARNING, UNKNOWN) and get_asset_staleness for staleness root causes. "
        "To diagnose missed materializations (asset expected to materialize but "
        "didn't): (1) get_asset_condition_evaluations with limit=1 for the "
        "latest evaluation, (2) walk evaluationNodes from rootUniqueId — find "
        "the node where numTrue=0 that should be >0, userLabel/expandedLabel "
        "identifies which rule blocked it, (3) if the condition tree looks "
        "correct, get_tick_history for the sensor to check for errors or skips. "
        "Mutation tools (launch_run, launch_multiple_runs, "
        "reexecute_run) require confirm=True to execute — always preview first "
        "with confirm=False."
    ),
    lifespan=_lifespan,
)


class GraphQLError(Exception):
    """Structured error from the Dagster+ GraphQL API."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message)
        self.message = message
        self.details = details


async def gql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query against the Dagster+ API."""
    if _client is None:
        raise RuntimeError("HTTP client not initialized (lifespan not started)")
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
