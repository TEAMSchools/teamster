#!/bin/bash

# inject 1Password secrets
source ./.devcontainer/scripts/inject-secrets.sh

# Strip 1Password SA token from future shells — inject-secrets.sh has already run
echo 'unset OP_SERVICE_ACCOUNT_TOKEN' >>/home/vscode/.bashrc
echo 'unset OP_SERVICE_ACCOUNT_TOKEN' >>/home/vscode/.profile

uv self update # reliable enough to not pin a version
uv tool upgrade --all
uv sync --frozen --all-groups

# install trunk tools
/workspaces/teamster/trunk install
