#!/bin/bash

# Auth headers for Dagster's official hosted MCP server, consumed by the
# `headersHelper` field in .mcp.json. Claude Code runs this at connection time,
# parses stdout as a JSON object of string headers, and gives up after 10s.
#
# The 1Password reference lives only in dagster-mcp-launch.sh. Sourcing that
# with --no-exec reuses its fetch without starting the homebrew server, so the
# token exists solely in this short-lived subprocess -- never in the
# environment, never written to a config file.

set -euo pipefail

source "$(dirname "$0")/dagster-mcp-launch.sh" --no-exec

jq -n \
	--arg token "${DAGSTER_CLOUD_API_TOKEN}" \
	--arg org "${DAGSTER_CLOUD_ORGANIZATION_ID}" \
	'{Authorization: ("Bearer " + $token), "Dagster-Cloud-Organization": $org}'
