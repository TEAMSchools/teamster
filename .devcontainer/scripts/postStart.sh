#!/bin/bash

# inject 1Password secrets into .env
op inject -f --in-file=.devcontainer/tpl/.env.tpl --out-file=env/.env

# update pip
python -m pip install --no-cache-dir --upgrade pip

# update pdm
sudo /usr/local/py-utils/bin/pdm self update

# update trunk
trunk upgrade -y --no-progress

# set default kubectl context
kubectl config set-context --current --namespace=dagster-cloud
