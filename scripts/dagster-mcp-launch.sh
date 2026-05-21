#!/bin/bash

# Launch dagster_plus_mcp with a scoped Dagster Cloud API token.
# Reads the 1Password service account token from the tmpfs file written by
# postStart.sh, exchanges it for DAGSTER_CLOUD_API_TOKEN via `op read`, and
# execs the MCP server. OP_SERVICE_ACCOUNT_TOKEN never enters the MCP process
# env; it lives only in the brief `op read` subprocess.
set -euo pipefail

token="$(</etc/secret-volume/.op-token)"
if [[ -z ${token} || ${token} == "revoked-after-injection" ]]; then
  echo "dagster MCP: OP token unavailable — rebuild Codespace to re-provision" >&2
  exit 1
fi

DAGSTER_CLOUD_API_TOKEN="$(OP_SERVICE_ACCOUNT_TOKEN="${token}" \
  op read 'op://Data Team/Dagster Cloud Agent/credential')"
unset token

export DAGSTER_CLOUD_API_TOKEN
export DAGSTER_CLOUD_ORGANIZATION_ID=kipptaf
export DAGSTER_CLOUD_DEPLOYMENT=prod

exec uv run --group dev python -m dagster_plus_mcp
