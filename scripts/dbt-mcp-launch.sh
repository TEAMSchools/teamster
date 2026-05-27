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

# Static config (DBT_HOST*, DBT_ACCOUNT_ID, DBT_PROD_ENV_ID, DISABLE_DBT_CLI,
# DISABLE_TOOLS) lives in .mcp.json's `env` block. Notes on the choices there:
# - DBT_PROJECT_DIR / DBT_PATH intentionally unset so boot skips the ~3.4s
#   `dbt lsp --help` Fusion probe (lsp_binary_manager.detect_fusion_lsp).
# - DISABLE_TOOLS lists every proxied tool: empty configured_proxied_tools
#   short-circuits register_proxied_tools before its POST /api/ai/v1/mcp/ 403s
#   our service token (legacy Team plan — no Developer scope; remote MCP not
#   available on this plan tier).

exec uvx dbt-mcp
