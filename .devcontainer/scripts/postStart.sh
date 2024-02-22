#!/bin/bash

# inject 1Password secrets into .env
op inject -f --in-file=.devcontainer/tpl/.env.tpl --out-file=env/.env

# update apt packages
sudo apt-get -y --no-install-recommends update &&
  sudo apt-get -y --no-install-recommends upgrade &&
  sudo apt-get -y autoremove &&
  sudo apt-get -y clean

# update pip
python -m pip install --no-cache-dir --upgrade pip

# update pdm
sudo /usr/local/py-utils/bin/pdm self update

# update trunk
trunk upgrade -y --no-progress

# 1password cli completions
# trunk-ignore(shellcheck/SC1090,shellcheck/SC2312)
source <(op completion bash)

# set default kubectl context
kubectl config set-context --current --namespace=dagster-cloud
