#!/bin/bash

# export dev envvars
export PYTHONDONTWRITEBYTECODE=1
export USE_GKE_GCLOUD_AUTH_PLUGIN=True
export DBT_PROFILES_DIR=/workspaces/teamster/.dbt

# update apt packages
sudo apt-get -y --no-install-recommends update &&
  sudo apt-get -y --no-install-recommends upgrade &&
  sudo apt-get -y autoremove &&
  sudo apt-get -y clean

# update pip
python -m pip install --no-cache-dir --upgrade pip

# update pdm
sudo /usr/local/py-utils/bin/pdm self update

# install pdm dependencies
pdm install --no-lock

# update trunk
trunk upgrade -y --no-progress
