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

Runs via `.mcp.json` with `uv run --group mcp python -m dagster_plus`. Requires
`PYTHONPATH=/workspaces/teamster/mcp` in the `env` block — `cwd` alone doesn't
add to the Python import path. The `DAGSTER_CLOUD_API_TOKEN` is fetched at
launch via `op read`, which requires a valid `OP_SERVICE_ACCOUNT_TOKEN` in the
environment.

### Dagster asset statuses

- **Degraded** = latest materialization failed. Use `list_runs` with
  `statuses=["FAILURE"]`, then verify each candidate by fetching the most recent
  run per job (`list_runs` with `job_name=..., limit=1`, no status filter) —
  bulk cross-referencing capped result sets misses retries and recoveries.
- **Stale** = upstream data/code/dependencies changed since last
  materialization. Use `list_stale_assets`.

## BigQuery MCP

The BigQuery MCP tool truncates results at 50 rows. When querying
`INFORMATION_SCHEMA.COLUMNS` for tables with >50 columns, paginate with
`WHERE ordinal_position > N` to get all rows.
