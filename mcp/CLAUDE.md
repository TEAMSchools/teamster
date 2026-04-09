# CLAUDE.md — `mcp/`

## Overview

MCP servers configured in `.mcp.json`. The `dagster_plus` package is the only
locally-developed server — others (BigQuery, dbt, GKE) are external tools.

## MCP Tool Selection

For ad-hoc queries against known production tables (no `ref()` needed), use the
BigQuery MCP directly. Use dbt MCP's `show` only when `ref()` / `source()`
resolution is needed — it adds compilation overhead and the target determines
the environment.

## Dagster+ MCP

See `dagster_plus/CLAUDE.md` for package structure, schema gotchas, and mutation
patterns.

### Dagster asset statuses

- **Degraded** = latest materialization failed. Use `get_asset_health` for
  specific assets, or `list_runs` with `statuses=["FAILURE"]` to find recent
  failures across all assets, then verify each candidate by fetching the most
  recent run per job (`list_runs` with `job_name=..., limit=1`, no status
  filter) — bulk cross-referencing capped result sets misses retries and
  recoveries.
- **Stale** = upstream data/code/dependencies changed since last
  materialization. Use `search_assets` to discover assets by prefix, then
  `get_asset_staleness` for specific assets.

## Observability MCP (`@google-cloud/observability-mcp`)

Covers Cloud Logging, Monitoring, Trace, and Error Reporting for
`teamster-332318`. Uses ADC (same as BigQuery/GKE). Tools: `list_group_stats`
(Error Reporting), `list_log_entries`, `list_alerts`, `list_alert_policies`,
`list_time_series`, etc.

Uses the same `CodespacesRole` custom IAM role as the GKE MCP. If any tool
returns permission denied, the role is missing that API's permission — flag it
to the user, don't assume no data.

For pod-level log queries, prefer `mcp__gke__query_logs` over
`mcp__observability__list_log_entries` — the GKE MCP returns pod labels (run-id,
op, code-location) that the observability MCP may not surface.

## GKE MCP

Authenticates via ADC as **impersonated service account**
`codespaces@teamster-332318.iam.gserviceaccount.com` — not the user's gcloud
identity. Permissions are on the `CodespacesRole` custom IAM role. If calls
return `PermissionDenied`, check that role, not user IAM bindings.

`mcp__gke__query_logs` uses snake_case keys in `time_range` (`start_time`,
`end_time`), not camelCase. Results cap at 100 — paginate by using the last
entry's timestamp as the next `start_time`.

## BigQuery MCP

The BigQuery MCP tool truncates results at 50 rows. When querying
`INFORMATION_SCHEMA.COLUMNS` for tables with >50 columns, paginate with
`WHERE ordinal_position > N` to get all rows.
