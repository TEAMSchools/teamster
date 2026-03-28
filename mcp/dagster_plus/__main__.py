"""Entry point for the Dagster+ MCP server."""

from . import tools  # noqa: F401 — triggers decorator registration
from .server import server

server.run(transport="stdio")
