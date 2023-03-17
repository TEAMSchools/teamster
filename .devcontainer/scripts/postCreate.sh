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

# export GCP service account key to file
mkdir -p ./env
echo "${GCP_SERVICE_ACCOUNT_KEY}" >env/service-account.json

# authenticate gcloud
gcloud auth activate-service-account --key-file=env/service-account.json

# set gcloud project & region
gcloud config set project "$(jq -r .project_id env/service-account.json)"
gcloud config set compute/region "${GCP_REGION}"

# install kubectl authentication plugin
sudo apt-get -qq -y install --no-install-recommends google-cloud-sdk-gke-gcloud-auth-plugin &&
  sudo apt-get -qq autoremove -y &&
  sudo apt-get -qq clean -y

# update the kubectl configuration to use the plugin
gcloud container clusters get-credentials dagster-cloud

echo "

# postCreate.sh
GCP_PROJECT_ID=\"$(jq -r .project_id env/service-account.json)\"
export GCP_PROJECT_ID

GCP_PROJECT_NUMER=$(
  gcloud projects list \
    --filter="$(gcloud config get-value project)" \
    --format="value(PROJECT_NUMBER)"
)
export GCP_PROJECT_NUMER

# do not write .pyc files on the import of source modules
export PYTHONDONTWRITEBYTECODE=1
" >>"${HOME}/.bashrc
"

# initialize dbt submodule
git submodule init
git submodule update
