# CLAUDE.md — `mcp/`

## Overview

MCP (Model Context Protocol) servers that expose Dagster+ operational data to AI
assistants. Each server is a Python package or script run via `uv run`.

## MCP Tool Selection

For ad-hoc queries against known production tables (no `ref()` needed), use the
BigQuery MCP directly. Use dbt MCP's `show` only when `ref()` / `source()`
resolution is needed — it adds compilation overhead and the target determines
the environment.

## Dagster+ MCP

Launched via `mcp/dagster_plus/run.sh`, which fetches `DAGSTER_CLOUD_API_TOKEN`
via `op read` (requires a valid `OP_SERVICE_ACCOUNT_TOKEN`) and execs
`uv run --project mcp python -m dagster_plus`. The `mcp/` directory has its own
`pyproject.toml` so `dagster_plus` is a proper installable package — no
`PYTHONPATH` needed.

### Dagster asset statuses

- **Degraded** = latest materialization failed. Use `get_asset_health` for
  specific assets, or `list_runs` with `statuses=["FAILURE"]` to find recent
  failures across all assets, then verify each candidate by fetching the most
  recent run per job (`list_runs` with `job_name=..., limit=1`, no status
  filter) — bulk cross-referencing capped result sets misses retries and
  recoveries.
- **Stale** = upstream data/code/dependencies changed since last
  materialization. Use `get_asset_staleness` for specific assets. Use
  `search_assets` to discover assets by prefix, then drill in. Avoid
  `list_stale_assets` (fetches entire graph, can exceed token limits).

## BigQuery MCP

The BigQuery MCP tool truncates results at 50 rows. When querying
`INFORMATION_SCHEMA.COLUMNS` for tables with >50 columns, paginate with
`WHERE ordinal_position > N` to get all rows.
