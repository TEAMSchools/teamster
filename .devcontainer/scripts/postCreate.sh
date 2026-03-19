#!/bin/bash

git config pull.rebase false # specify how to reconcile divergent branches (merge)
git config push.autoSetupRemote true

# install extra apt packages
sudo apt-get update -y &&
  sudo apt-get -y install --no-install-recommends sshpass &&
  sudo apt-get -y clean &&
  sudo rm -rf /var/lib/apt/lists/*

# create env folder
mkdir -p ./env
sudo mkdir -p /etc/secret-volume

# restrict permissions on secrets-related paths
chmod 755 .devcontainer/scripts/inject-secrets.sh
chmod 600 .devcontainer/tpl/*
chmod 700 ./env
sudo chmod 700 /etc/secret-volume

# set up trunk
chmod +x /workspaces/teamster/trunk

# install uv -- ignoring feature bc it doesn't allow self update
curl -LsSf https://astral.sh/uv/install.sh | sh

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
