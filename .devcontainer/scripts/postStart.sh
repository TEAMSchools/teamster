#!/bin/bash

# inject 1Password secrets — only strip token from future shells if inject succeeded
if source ./.devcontainer/scripts/inject-secrets.sh; then
  echo 'unset OP_SERVICE_ACCOUNT_TOKEN' >>/home/vscode/.bashrc
  echo 'unset OP_SERVICE_ACCOUNT_TOKEN' >>/home/vscode/.profile
fi

set +euo pipefail

# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

uv self update # reliable enough to not pin a version
uv tool upgrade --all
uv sync --frozen --all-groups

# install trunk tools
/workspaces/teamster/trunk install
