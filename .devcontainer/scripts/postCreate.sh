#!/bin/bash

# specify how to reconcile divergent branches
git config pull.rebase false # merge

# update/install apt packages
sudo apt-get -y --no-install-recommends update &&
  sudo apt-get -y --no-install-recommends upgrade &&
  sudo apt-get -y --no-install-recommends install \
    bash-completion \
    google-cloud-cli-gke-gcloud-auth-plugin &&
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

# authenticate gcloud
gcloud auth activate-service-account --key-file=/etc/secret-volume/gcloud_service_account_json

# set gcloud project & region
gcloud config set project teamster-332318
gcloud config set compute/region us-central1

# update the kubectl configuration to use the plugin
gcloud container clusters get-credentials autopilot-cluster-dagster-hybrid-1

# install pdm dependencies
pdm install --frozen-lockfile

# install dbt deps and generate manifests
# trunk-ignore(shellcheck/SC2312)
find ./src/dbt/ -maxdepth 2 -name "dbt_project.yml" -print0 |
  while IFS= read -r -d "" file; do
    directory=$(dirname "${file}")
    project_name=$(basename "${directory}")

    pdm run dbt "${project_name}" deps && pdm run dbt "${project_name}" parse
  done

# install dbt cloud cli
# sudo pip install dbt
