#!/bin/bash

git config pull.rebase false # specify how to reconcile divergent branches (merge)
git config push.autoSetupRemote true

# install extra apt packages
sudo apt-get update -y &&
  sudo apt-get -y install --no-install-recommends sshpass &&
  sudo apt-get -y clean &&
  sudo rm -rf /var/lib/apt/lists/*

# install pyright for Claude Code LSP
npm install -g pyright

# create env folder
mkdir -p ./env

# restrict permissions on secrets-related paths
chmod 755 .devcontainer/scripts/inject-secrets.sh
chmod 600 .devcontainer/tpl/*
chmod 700 ./env

# restrict permissions on hook/config paths
chmod 644 .claude/settings.json
chmod 755 .claude/hooks/ .claude/hooks/*.sh

# set up trunk
chmod +x /workspaces/teamster/trunk

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

# install gke-mcp
curl --fail -L \
  https://github.com/GoogleCloudPlatform/gke-mcp/releases/download/v0.10.0/gke-mcp_Linux_x86_64.tar.gz \
  -o /tmp/gke-mcp.tar.gz ||
  {
    echo "❌ gke-mcp download failed"
    exit 1
  }
echo "93ade2e2fd73e767a9db407c4908e17871b54d222aebf570344f5a0535bd0868  /tmp/gke-mcp.tar.gz" |
  sha256sum -c - ||
  {
    echo "❌ gke-mcp checksum mismatch"
    exit 1
  }
tar --no-same-owner -xzf /tmp/gke-mcp.tar.gz -C /tmp gke-mcp
sudo install -m 0755 /tmp/gke-mcp /usr/local/bin/
rm /tmp/gke-mcp.tar.gz /tmp/gke-mcp

export DBT_SEND_ANONYMOUS_USAGE_STATS=false

# bootstrap dbt projects
(uv run dbt deps --project-dir=src/dbt/amplify &&
  uv run dbt parse --project-dir=src/dbt/amplify) &
(uv run dbt deps --project-dir=src/dbt/deanslist &&
  uv run dbt parse --project-dir=src/dbt/deanslist) &
(uv run dbt deps --project-dir=src/dbt/edplan &&
  uv run dbt parse --project-dir=src/dbt/edplan) &
(uv run dbt deps --project-dir=src/dbt/finalsite &&
  uv run dbt parse --project-dir=src/dbt/finalsite) &
(uv run dbt deps --project-dir=src/dbt/iready &&
  uv run dbt parse --project-dir=src/dbt/iready) &
(uv run dbt deps --project-dir=src/dbt/overgrad &&
  uv run dbt parse --project-dir=src/dbt/overgrad) &
(uv run dbt deps --project-dir=src/dbt/pearson &&
  uv run dbt parse --project-dir=src/dbt/pearson) &
(uv run dbt deps --project-dir=src/dbt/powerschool &&
  uv run dbt parse --project-dir=src/dbt/powerschool) &
(uv run dbt deps --project-dir=src/dbt/renlearn &&
  uv run dbt parse --project-dir=src/dbt/renlearn) &
(uv run dbt deps --project-dir=src/dbt/titan &&
  uv run dbt parse --project-dir=src/dbt/titan) &
(uv run dbt deps --project-dir=src/dbt/kippcamden &&
  uv run dbt parse --project-dir=src/dbt/kippcamden) &
(uv run dbt deps --project-dir=src/dbt/kippmiami &&
  uv run dbt parse --project-dir=src/dbt/kippmiami) &
(uv run dbt deps --project-dir=src/dbt/kippnewark &&
  uv run dbt parse --project-dir=src/dbt/kippnewark) &
(uv run dbt deps --project-dir=src/dbt/kipppaterson &&
  uv run dbt parse --project-dir=src/dbt/kipppaterson) &
(uv run dbt deps --project-dir=src/dbt/kipptaf &&
  uv run dbt parse --project-dir=src/dbt/kipptaf) &
wait

# transfer tmpfs ownership to vscode
sudo chown vscode:vscode /etc/secret-volume

# inject secrets
.devcontainer/scripts/inject-secrets.sh

# create convenience symlinks (-n: don't follow existing symlink-to-directory)
ln -sfn /etc/secret-volume /workspaces/teamster/secret-volume
ln -sfn /etc/secret-volume/.env /workspaces/teamster/env/.env
mkdir -p /tmp/dagster
ln -sfn /tmp/dagster /workspaces/teamster/dagster-tmp

# remove sudo — must be last privileged step
sudo rm -f /usr/local/bin/sudo /usr/bin/sudo
