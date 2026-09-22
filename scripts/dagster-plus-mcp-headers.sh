#!/bin/bash

# Auth headers for Dagster's official hosted MCP server, consumed by the
# `headersHelper` field in .mcp.json. Claude Code runs this at connection time,
# parses stdout as a JSON object of string headers, and gives up after 10s.
#
# The 1Password reference lives only in dagster-mcp-launch.sh. Sourcing that
# with --no-exec reuses its fetch without starting the homebrew server, so the
# token lives and dies with this process: exported here, inherited by jq, gone
# in under a second. It never reaches a persistent shell and is never written
# to a config file.

set -euo pipefail

source "$(dirname "$0")/dagster-mcp-launch.sh" --no-exec

jq -n \
	--arg token "${DAGSTER_CLOUD_API_TOKEN}" \
	--arg org "${DAGSTER_CLOUD_ORGANIZATION_ID}" \
	'{Authorization: ("Bearer " + $token), "Dagster-Cloud-Organization": $org}'
