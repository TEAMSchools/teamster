#!/bin/bash

git config pull.rebase false # specify how to reconcile divergent branches (merge)
git config push.autoSetupRemote true

# rm broken yarn key
sudo rm /etc/apt/sources.list.d/yarn.list

# install extra apt packages
sudo apt-get -y install --no-install-recommends sshpass &&
  sudo apt-get -y clean &&
  sudo rm -rf /var/lib/apt/lists/*

# create env folder
mkdir -p ./env
sudo mkdir -p /etc/secret-volume

# inject 1Password secrets
source ./.devcontainer/scripts/inject-secrets.sh

# set up trunk
chmod +x /workspaces/teamster/trunk
/workspaces/teamster/trunk install

# install dependencies
uv tool install datamodel-code-generator
uv tool install dagster-dg
uv sync --frozen

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
