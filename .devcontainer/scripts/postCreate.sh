#!/bin/bash

# override machine-scoped settings seeded by devcontainer features
MACHINE_SETTINGS="/home/vscode/.vscode-remote/data/Machine/settings.json"
mkdir -p "$(dirname "${MACHINE_SETTINGS}")"
[[ -f ${MACHINE_SETTINGS} ]] || echo '{}' >"${MACHINE_SETTINGS}"
jq '. + {"python.defaultInterpreterPath": "/workspaces/teamster/.venv/bin/python", "[python]": {"editor.defaultFormatter": "trunk.io"}}' \
  "${MACHINE_SETTINGS}" \
  >/tmp/machine-settings.json &&
  mv /tmp/machine-settings.json "${MACHINE_SETTINGS}"

# configure git
git config pull.rebase false # specify how to reconcile divergent branches (merge)
git config push.autoSetupRemote true

# install post-merge hook for future manifest regeneration
cp .vscode/scripts/post-merge.sh .git/hooks/post-merge
chmod +x .git/hooks/post-merge

# install extra apt packages
sudo apt-get update -y &&
  sudo apt-get -y install --no-install-recommends sshpass &&
  sudo apt-get -y clean &&
  sudo rm -rf /var/lib/apt/lists/*

# create env folder
mkdir -p ./env

# restrict permissions on secrets-related paths
chmod 700 ./env

# restrict permissions on hook/config paths
chmod 644 .claude/settings.json
chmod 755 .claude/hooks/ .claude/hooks/*.sh

# install uv -- ignoring feature bc it doesn't allow self update
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-install.sh &&
  sh /tmp/uv-install.sh &&
  rm /tmp/uv-install.sh

# add uv to PATH for this shell session
# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

# install uv dependencies
uv tool install datamodel-code-generator
uv tool install dagster-dg
uv tool install dbt-mcp
uv sync --frozen --all-groups

# bootstrap dbt packages
export DBT_SEND_ANONYMOUS_USAGE_STATS=false
uv run dbt deps --project-dir=src/dbt/amplify &
uv run dbt deps --project-dir=src/dbt/deanslist &
uv run dbt deps --project-dir=src/dbt/edplan &
uv run dbt deps --project-dir=src/dbt/finalsite &
uv run dbt deps --project-dir=src/dbt/iready &
uv run dbt deps --project-dir=src/dbt/overgrad &
uv run dbt deps --project-dir=src/dbt/pearson &
uv run dbt deps --project-dir=src/dbt/powerschool &
uv run dbt deps --project-dir=src/dbt/renlearn &
uv run dbt deps --project-dir=src/dbt/titan &
uv run dbt deps --project-dir=src/dbt/kippcamden &
uv run dbt deps --project-dir=src/dbt/kippmiami &
uv run dbt deps --project-dir=src/dbt/kippnewark &
uv run dbt deps --project-dir=src/dbt/kipppaterson &
uv run dbt deps --project-dir=src/dbt/kipptaf &
wait

# generate prod manifests for Power User --defer
for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  uv run dbt parse --target prod \
    --project-dir "src/dbt/${project}" \
    --profiles-dir .dbt \
    --target-path target/prod &
done
wait

# set up trunk
chmod +x /workspaces/teamster/trunk

# install pyright for Claude Code LSP
npm install -g pyright

# install MCP toolbox
curl --fail -O https://storage.googleapis.com/genai-toolbox/v0.29.0/linux/amd64/toolbox ||
  {
    echo "❌ MCP toolbox download failed"
    exit 1
  }
echo "8cb1cacbbaccf0940926643482d20e3b02efba80d1c93eafb4342079b1ebee95  toolbox" |
  sha256sum -c - ||
  {
    echo "❌ MCP toolbox checksum mismatch"
    exit 1
  }
chmod +x toolbox
sudo mv toolbox /usr/local/bin/

# fix tmpfs permissions (Codespaces may override tmpfs-mode from mount config)
sudo chmod 755 /etc/secret-volume
sudo chown vscode:vscode /etc/secret-volume

# create convenience symlinks (-n: don't follow existing symlink-to-directory)
ln -sfn /etc/secret-volume /workspaces/teamster/secret-volume
mkdir -p /tmp/dagster
ln -sfn /tmp/dagster /workspaces/teamster/dagster-tmp

# save 1Password token for on-demand use (conftest.py reads this at test time)
echo "${OP_SERVICE_ACCOUNT_TOKEN}" >/etc/secret-volume/.op-token
chmod 600 /etc/secret-volume/.op-token

# remove sudo — must be last privileged step
sudo rm -f /usr/local/bin/sudo /usr/bin/sudo
