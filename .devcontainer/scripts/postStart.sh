#!/bin/bash

# inject 1Password secrets — only strip token from future shells if inject succeeded
if ./.devcontainer/scripts/inject-secrets.sh; then
  echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >>/home/vscode/.bashrc
  echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >>/home/vscode/.profile
fi

set +euo pipefail

# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

uv self update # reliable enough to not pin a version
uv tool upgrade --all
uv sync --frozen --all-groups

# install trunk tools
/workspaces/teamster/trunk install --verbose
