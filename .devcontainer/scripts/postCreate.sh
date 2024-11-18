#!/bin/bash

# specify how to reconcile divergent branches
git config pull.rebase false # merge

# update/install apt packages
sudo apt-get -y --no-install-recommends update &&
  sudo apt-get -y --no-install-recommends upgrade &&
  sudo apt-get -y --no-install-recommends install \
    bash-completion &&
  sudo rm -rf /var/lib/apt/lists/*

# create env folder
mkdir -p ./env
mkdir -p /home/vscode/.dbt
sudo mkdir -p /etc/secret-volume

# inject 1Password secrets into .env
op inject -f --in-file=.devcontainer/tpl/.env.tpl --out-file=env/.env

# save secrets to file
op inject -f --in-file=.devcontainer/tpl/adp_wfn_cert.tpl \
  --out-file=env/adp_wfn_cert &&
  sudo mv -f env/adp_wfn_cert /etc/secret-volume/adp_wfn_cert

op inject -f --in-file=.devcontainer/tpl/adp_wfn_key.tpl \
  --out-file=env/adp_wfn_key &&
  sudo mv -f env/adp_wfn_key /etc/secret-volume/adp_wfn_key

op inject -f --in-file=.devcontainer/tpl/dbt_user_creds_json.tpl \
  --out-file=env/dbt_user_creds_json &&
  sudo mv -f env/dbt_user_creds_json /etc/secret-volume/dbt_user_creds_json

op inject -f --in-file=.devcontainer/tpl/deanslist_api_key_map_yaml.tpl \
  --out-file=env/deanslist_api_key_map_yaml &&
  sudo mv -f env/deanslist_api_key_map_yaml \
    /etc/secret-volume/deanslist_api_key_map_yaml

op inject -f --in-file=.devcontainer/tpl/gcloud_service_account_json.tpl \
  --out-file=env/gcloud_service_account_json &&
  sudo mv -f env/gcloud_service_account_json \
    /etc/secret-volume/gcloud_service_account_json

op inject -f --in-file=.devcontainer/tpl/id_rsa_egencia.tpl \
  --out-file=env/id_rsa_egencia &&
  sudo mv -f env/id_rsa_egencia /etc/secret-volume/id_rsa_egencia

op inject -f --in-file=.devcontainer/tpl/op_credentials_json.tpl \
  --out-file=env/op_credentials_json &&
  sudo mv -f env/op_credentials_json /etc/secret-volume/op_credentials_json

op inject -f --in-file=.devcontainer/tpl/dbt_cloud.yml.tpl \
  --out-file=env/dbt_cloud.yml &&
  sudo mv -f env/dbt_cloud.yml /home/vscode/.dbt/dbt_cloud.yml

# install pdm dependencies
pdm install --frozen-lockfile

# prepare dbt projects
pdm run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kippcamden/__init__.py
pdm run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kippmiami/__init__.py
pdm run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kippnewark/__init__.py
pdm run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py

# install dbt deps for packages
pdm run dbt deanslist deps
pdm run dbt edplan deps
pdm run dbt iready deps
pdm run dbt overgrad deps
pdm run dbt pearson deps
pdm run dbt powerschool deps
pdm run dbt renlearn deps
pdm run dbt titan deps
