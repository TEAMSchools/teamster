#!/bin/bash

# update apt packages
sudo apt-get -qq -y update --no-install-recommends &&
  sudo apt-get -qq -y install --no-install-recommends bash-completion &&
  sudo apt-get -qq -y upgrade --no-install-recommends &&
  sudo apt-get -qq autoremove -y &&
  sudo apt-get -qq clean -y

# update pip
python -m pip install --no-cache-dir --upgrade pip

# install Trunk
# trunk-ignore(shellcheck/SC2312)
curl https://get.trunk.io -fsSL | bash -s -- -y
trunk install --ci

# install pdm dependencies
pdm config strategy.update eager
pdm install --no-self

# commit new files
git config pull.rebase false
git add .
git commit -m "Initial PDM commit"
git push

# create env folder
mkdir -p ./env
sudo mkdir -p /etc/secret-volume

# save secrets to file
echo "${GCLOUD_SERVICE_ACCOUNT_KEY}" >env/gcloud-service-account.json
echo "${DEANSLIST_API_KEY_MAP}" |
  sudo tee /etc/secret-volume/deanslist_api_key_map_yaml >/dev/null

# authenticate gcloud
gcloud auth activate-service-account --key-file=env/gcloud-service-account.json

# set gcloud project & region
gcloud config set project "${GCP_PROJECT_ID}"
gcloud config set compute/region "${GCP_REGION}"

# install kubectl authentication plugin
sudo apt-get -qq -y install --no-install-recommends google-cloud-sdk-gke-gcloud-auth-plugin &&
  sudo apt-get -qq autoremove -y &&
  sudo apt-get -qq clean -y

# update the kubectl configuration to use the plugin
gcloud container clusters get-credentials dagster-cloud

# initialize dbt submodule
git submodule init
git submodule update --remote
