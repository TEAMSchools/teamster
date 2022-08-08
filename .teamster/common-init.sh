#!/bin/bash

# create base .env file
cp ./env/common.env.tmpl ./env/common.env

# setup pre-commit hook
cat <<EOT >>./.git/hooks/pre-commit
pdm run envsubst < ./.dagster/cloud-workspace-gh.yaml.tmpl > ./.dagster/cloud-workspace-gh.yaml
git add ./.dagster/cloud-workspace-gh.yaml
EOT
chmod +x ./.git/hooks/pre-commit
