#!/bin/bash

# persist 1Password token for on-demand use (conftest.py reads this at test time)
echo "${OP_SERVICE_ACCOUNT_TOKEN}" >/etc/secret-volume/.op-token
chmod 600 /etc/secret-volume/.op-token

# revoke 1Password tokens from future interactive shells
grep -qF 'OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' /home/vscode/.bashrc ||
  echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >>/home/vscode/.bashrc
grep -qF 'OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' /home/vscode/.profile ||
  echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >>/home/vscode/.profile
grep -qF 'OP_CONNECT_TOKEN=revoked-after-injection' /home/vscode/.bashrc ||
  echo 'export OP_CONNECT_TOKEN=revoked-after-injection' >>/home/vscode/.bashrc
grep -qF 'OP_CONNECT_TOKEN=revoked-after-injection' /home/vscode/.profile ||
  echo 'export OP_CONNECT_TOKEN=revoked-after-injection' >>/home/vscode/.profile

set +euo pipefail

# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

uv self update # reliable enough to not pin a version
uv tool upgrade --all
uv sync --frozen --all-groups

# install trunk tools
/workspaces/teamster/trunk install --verbose
