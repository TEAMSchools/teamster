#!/bin/bash

# Launch the official Tableau MCP server (@tableau/mcp-server).
# Reads the 1Password service account token from the tmpfs file written by
# postStart.sh, exchanges it for the Tableau connection config via `op read`
# (1Password item "Tableau Server PAT - Dagster" in the Data Team vault, the
# same item Dagster's op-tableau-server-api k8s secret maps to), and execs it.
# OP_SERVICE_ACCOUNT_TOKEN never enters the MCP process env; it lives only in
# the brief `op read` subprocesses.
set -euo pipefail

token="$(</etc/secret-volume/.op-token)"
if [[ -z ${token} || ${token} == "revoked-after-injection" ]]; then
  echo "tableau MCP: OP token unavailable — rebuild Codespace to re-provision" >&2
  exit 1
fi

SERVER="$(OP_SERVICE_ACCOUNT_TOKEN="${token}" \
  op read 'op://Data Team/Tableau Server PAT - Dagster/hostname')"
SITE_NAME="$(OP_SERVICE_ACCOUNT_TOKEN="${token}" \
  op read 'op://Data Team/Tableau Server PAT - Dagster/site id')"
PAT_NAME="$(OP_SERVICE_ACCOUNT_TOKEN="${token}" \
  op read 'op://Data Team/Tableau Server PAT - Dagster/username')"
PAT_VALUE="$(OP_SERVICE_ACCOUNT_TOKEN="${token}" \
  op read 'op://Data Team/Tableau Server PAT - Dagster/credential')"
unset token

export SERVER SITE_NAME PAT_NAME PAT_VALUE

# TRANSPORT lives in .mcp.json's `env` block.
exec npx -y @tableau/mcp-server@latest
