#!/bin/bash

# inject 1Password secrets — only strip token from future shells if inject succeeded
if ./.devcontainer/scripts/inject-secrets.sh; then
  echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >>/home/vscode/.bashrc
  echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >>/home/vscode/.profile
  echo 'export OP_CONNECT_TOKEN=revoked-after-injection' >>/home/vscode/.bashrc
  echo 'export OP_CONNECT_TOKEN=revoked-after-injection' >>/home/vscode/.profile
fi

set +euo pipefail

# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

uv self update # reliable enough to not pin a version
uv tool upgrade --all
uv sync --frozen --all-groups

# install trunk tools
/workspaces/teamster/trunk install --verbose

# generate prod manifests for Power User --defer
for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  uv run dbt parse --target prod \
    --project-dir "src/dbt/${project}" \
    --profiles-dir .dbt \
    --target-path target/prod &
done
wait

# install post-merge hook for future manifest regeneration
cp .vscode/scripts/post-merge.sh .git/hooks/post-merge
chmod +x .git/hooks/post-merge
