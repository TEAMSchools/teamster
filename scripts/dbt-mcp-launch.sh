#!/bin/bash

# Launch dbt-mcp with dbt Cloud platform credentials.
# Reads the 1Password service account token from the tmpfs file written by
# postStart.sh, exchanges it for DBT_TOKEN via `op read`, and execs the MCP
# server. OP_SERVICE_ACCOUNT_TOKEN never enters the MCP process env.
set -euo pipefail

token="$(</etc/secret-volume/.op-token)"
if [[ -z ${token} || ${token} == "revoked-after-injection" ]]; then
  echo "dbt MCP: OP token unavailable — rebuild Codespace to re-provision" >&2
  exit 1
fi

DBT_TOKEN="$(OP_SERVICE_ACCOUNT_TOKEN="${token}" \
  op read 'op://Data Team/dbt Cloud Service Token - Codespaces/credential')"
unset token

export DBT_TOKEN
export DBT_HOST=rn998.us1.dbt.com
export DBT_ACCOUNT_ID=116510
export DBT_PROD_ENV_ID=70403104014899
export DBT_PROJECT_DIR=/workspaces/teamster/src/dbt/kipptaf
export DBT_PATH=/workspaces/teamster/.venv/bin/dbt

exec uvx dbt-mcp
