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

server = FastMCP("dagster-plus")


def gql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query against the Dagster+ API."""
    with httpx.Client(timeout=60) as client:
        response = client.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables or {}},
            headers={
                "Dagster-Cloud-Api-Token": DAGSTER_CLOUD_API_TOKEN,
                "Content-Type": "application/json",
            },
        )
        if not response.is_success:
            raise RuntimeError(
                f"Dagster API {response.status_code}: {response.text[:500]}"
            )
        data = response.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data["data"]
