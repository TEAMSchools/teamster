#!/bin/bash

# update/install apt packages
sudo apt-get -y --no-install-recommends update &&
  sudo apt-get -y --no-install-recommends upgrade &&
  sudo apt-get -y --no-install-recommends install \
    bash-completion \
    google-cloud-sdk-gke-gcloud-auth-plugin &&
  sudo apt-get -y autoremove &&
  sudo apt-get -y clean

# create env folder
mkdir -p ./env
sudo mkdir -p /etc/secret-volume

# save secrets to file
echo "${GCLOUD_SERVICE_ACCOUNT_KEY}" >env/gcloud_service_account_json
echo "${DBT_USER_CREDS}" |
  sudo tee /etc/secret-volume/dbt_user_creds_json >/dev/null
echo "${DEANSLIST_API_KEY_MAP}" |
  sudo tee /etc/secret-volume/deanslist_api_key_map_yaml >/dev/null

# update pip
python -m pip install --no-cache-dir --upgrade pip

# authenticate gcloud
gcloud auth activate-service-account --key-file=env/gcloud-service-account.json

# set gcloud project & region
gcloud config set project teamster-332318
gcloud config set compute/region us-central1

# update the kubectl configuration to use the plugin
gcloud container clusters get-credentials dagster-cloud

# initialize dbt submodule
git submodule init
git submodule update --remote
