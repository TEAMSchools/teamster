#!/bin/bash

git config pull.rebase false # specify how to reconcile divergent branches (merge)
git config push.autoSetupRemote true

# add gcloud gpg key
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg || true
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# update/install apt packages
sudo apt-get -y --no-install-recommends update &&
  sudo apt-get -y --no-install-recommends upgrade &&
  sudo apt-get -y --no-install-recommends install bash-completion google-cloud-cli &&
  sudo rm -rf /var/lib/apt/lists/*

# create env folder
mkdir -p ./env
sudo mkdir -p /etc/secret-volume

# inject 1Password secrets into .env
op inject -f --in-file=.devcontainer/tpl/.env.tpl --out-file=env/.env

# save secrets to file
op inject -f --in-file=.devcontainer/tpl/adp_wfn_api.cer.tpl \
  --out-file=env/adp_wfn_api.cer &&
  sudo mv -f env/adp_wfn_api.cer /etc/secret-volume/adp_wfn_api.cer

op inject -f --in-file=.devcontainer/tpl/adp_wfn_api.key.tpl \
  --out-file=env/adp_wfn_api.key &&
  sudo mv -f env/adp_wfn_api.key /etc/secret-volume/adp_wfn_api.key

op inject -f --in-file=.devcontainer/tpl/deanslist_api_key_map_yaml.tpl \
  --out-file=env/deanslist_api_key_map_yaml &&
  sudo mv -f env/deanslist_api_key_map_yaml \
    /etc/secret-volume/deanslist_api_key_map_yaml

op inject -f --in-file=.devcontainer/tpl/id_rsa_egencia.tpl \
  --out-file=env/id_rsa_egencia &&
  sudo mv -f env/id_rsa_egencia /etc/secret-volume/id_rsa_egencia

op inject -f --in-file=.devcontainer/tpl/powerschool_ssh_password.txt.tpl \
  --out-file=env/powerschool_ssh_password.txt &&
  sudo mv -f env/powerschool_ssh_password.txt /etc/secret-volume/powerschool_ssh_password.txt

# install uv
curl -LsSf https://astral.sh/uv/install.sh | sh || true

# install dependencies
uv tool install datamodel-code-generator
uv tool install dagster-dg
uv sync

# prepare dbt projects
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kippcamden/__init__.py &&
  sudo mkdir -p /gcs/kippcamden &&
  sudo cp src/dbt/kippcamden/target/manifest.json /gcs/kippcamden/manifest.json
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kippmiami/__init__.py &&
  sudo mkdir -p /gcs/kippmiami &&
  sudo cp src/dbt/kippmiami/target/manifest.json /gcs/kippmiami/manifest.json
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kippnewark/__init__.py &&
  sudo mkdir -p /gcs/kippnewark &&
  sudo cp src/dbt/kippnewark/target/manifest.json /gcs/kippnewark/manifest.json
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py &&
  sudo mkdir -p /gcs/kipptaf &&
  sudo cp src/dbt/kipptaf/target/manifest.json /gcs/kipptaf/manifest.json

# install dbt deps for packages
uv run dbt deps --project-dir=src/dbt/deanslist
uv run dbt deps --project-dir=src/dbt/edplan
uv run dbt deps --project-dir=src/dbt/iready
uv run dbt deps --project-dir=src/dbt/overgrad
uv run dbt deps --project-dir=src/dbt/pearson
uv run dbt deps --project-dir=src/dbt/powerschool
uv run dbt deps --project-dir=src/dbt/renlearn
uv run dbt deps --project-dir=src/dbt/titan
