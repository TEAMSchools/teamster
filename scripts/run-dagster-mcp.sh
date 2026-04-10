#!/usr/bin/env bash
DAGSTER_CLOUD_API_TOKEN=$(op read 'op://Data Team/Dagster Cloud Agent/credential')
export DAGSTER_CLOUD_API_TOKEN
exec uv run --group dev python -m dagster_plus_mcp
