# CLAUDE.md — `mcp/`

## Overview

MCP (Model Context Protocol) servers that expose Dagster+ operational data to AI
assistants. Each server is a Python package or script run via `uv run`.

## MCP Tool Selection

For ad-hoc queries against known production tables (no `ref()` needed), use the
BigQuery MCP directly. Use dbt MCP's `show` only when `ref()` / `source()`
resolution is needed — it adds compilation overhead and the target determines
the environment.

## BigQuery MCP

The BigQuery MCP tool truncates results at 50 rows. When querying
`INFORMATION_SCHEMA.COLUMNS` for tables with >50 columns, paginate with
`WHERE ordinal_position > N` to get all rows.
