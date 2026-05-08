#!/bin/bash

# Launch the Cube REST MCP server.
# Reads the 1Password service account token from the tmpfs file written by
# postStart.sh, exchanges it for the Cube Cloud API secret via `op read`, and
# execs the Python MCP server. The Python server signs a JWT per startup with
# CUBE_USER_EMAIL as the security context. OP_SERVICE_ACCOUNT_TOKEN never
# enters the MCP process env; it lives only in the brief `op read` subprocess.
set -euo pipefail

token="$(</etc/secret-volume/.op-token)"
if [[ -z ${token} || ${token} == "revoked-after-injection" ]]; then
  echo "cube-rest MCP: OP token unavailable — rebuild Codespace to re-provision" >&2
  exit 1
fi

CUBE_API_SECRET="$(OP_SERVICE_ACCOUNT_TOKEN="${token}" \
  op read 'op://Data Team/Cube Cloud REST API/credential')"
unset token

export CUBE_API_SECRET

exec uv run /workspaces/teamster/scripts/cube_rest_mcp.py
