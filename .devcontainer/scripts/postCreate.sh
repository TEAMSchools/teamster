#!/bin/bash

# update/install apt packages
sudo apt-get -y --no-install-recommends update &&
  sudo apt-get -y --no-install-recommends upgrade &&
  sudo apt-get -y --no-install-recommends install \
    bash-completion \
    google-cloud-sdk-gke-gcloud-auth-plugin &&
  sudo apt-get -y autoremove &&
  sudo apt-get -y clean

# export dev envvars
export PYTHONDONTWRITEBYTECODE=1
export USE_GKE_GCLOUD_AUTH_PLUGIN=True
export DBT_PROFILES_DIR=/workspaces/teamster/.dbt

# create env folder
mkdir -p ./env
sudo mkdir -p /etc/secret-volume

# save secrets to file
echo "${GCLOUD_SERVICE_ACCOUNT_KEY}" >env/gcloud-service-account.json
echo "${DBT_USER_CREDS}" |
  sudo tee /etc/secret-volume/dbt_user_creds_json >/dev/null
echo "${DEANSLIST_API_KEY_MAP}" |
  sudo tee /etc/secret-volume/deanslist_api_key_map_yaml >/dev/null

# update pip
python -m pip install --no-cache-dir --upgrade pip

# authenticate gcloud
gcloud auth activate-service-account --key-file=env/gcloud-service-account.json

# set gcloud project & region
gcloud config set project "${GCP_PROJECT_ID}"
gcloud config set compute/region "${GCP_REGION}"

# update the kubectl configuration to use the plugin
gcloud container clusters get-credentials dagster-cloud

# initialize dbt submodule
git submodule init
git submodule update --remote
