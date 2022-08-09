#!/bin/bash

# setup pre-commit hook
cat <<EOT >>./.git/hooks/pre-commit
pdm run envsubst < ./.dagster/cloud-workspace-gh.yaml.tmpl > ./.dagster/cloud-workspace-gh.yaml
git add ./.dagster/cloud-workspace-gh.yaml
EOT
chmod +x ./.git/hooks/pre-commit

# create GitHub Workload Identity Service Account role
export GH_WORKLOAD_IDENTITY_POOL_ID=$(
	gcloud iam workload-identity-pools describe github-pool \
		--location=global \
		--format="value(name)" \
		2>/dev/null
)

# create base .env file
envsubst < ./env/common.env.tmpl > ./env/common.env
