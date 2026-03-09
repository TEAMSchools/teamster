# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

**Zendesk** customer support platform integration.

**Note**: The asset factory (`build_ticket_metrics_archive`) is fully commented
out in `assets.py`. Only the resource, ops, and schema are active.

## Files

**`resources.py`** (`ZendeskResource`): HTTP client wrapping the Zendesk REST
API. Authenticates with `subdomain`, `email`, and API `token`. Implements `get`,
`post`, `put`, `delete`, and `list` (cursor-paginated). Handles rate limits via
`handle_rate_limits` / `handle_limit_exceeded`.

**`ops.py`**: Op definitions for Zendesk data operations.

**`schema.py`**: Pydantic models for Zendesk objects (`TicketMetric`,
`Minutes`).

**`assets.py`**: Commented-out asset factory (`build_ticket_metrics_archive`)
for monthly-partitioned ticket metrics archive. Disabled pending re-enablement.

## Notes

When re-enabling the asset factory, it uses `MonthlyPartitionsDefinition`
partitioned by month (July 2011 – June 2023) and writes Avro via
`io_manager_gcs_file`.
