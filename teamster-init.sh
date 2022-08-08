#!/bin/bash

read -p "Enter instance name: " INSTANCE_NAME

# create base .env file
mkdir -p ./env/${INSTANCE_NAME}
cp ./env/.env.tmpl ./env/${INSTANCE_NAME}/.env
sed -i "2s/.*/INSTANCE_NAME=${INSTANCE_NAME}/" ./env/${INSTANCE_NAME}/.env

# setup pre-commit hook
cat <<EOT >>./.git/hooks/pre-commit
pdm run envsubst < ./.dagster/cloud-workspace-gh.yaml.tmpl > ./.dagster/cloud-workspace-gh.yaml
git add ./.dagster/cloud-workspace-gh.yaml
EOT
chmod +x ./.git/hooks/pre-commit
