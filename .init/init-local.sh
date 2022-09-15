#!/bin/bash

read -r -p "Enter instance name: " instance_name

if [[ -z ${instance_name} ]]; then
	echo "<instance_name> is required"
	exit 1
else
	export INSTANCE_NAME=${instance_name}

	# create DC location file
	envsubst \
		<./.dagster/dagster-cloud.yaml.tmpl \
		>./.dagster/dagster-cloud-"${INSTANCE_NAME}".yaml

	# create GH workflow files
	envsubst \
		<./.github/workflows/deploy.yaml.tmpl \
		>./.github/workflows/deploy-"${INSTANCE_NAME}".yaml

	envsubst \
		<./.github/workflows/branch-deploy.yaml.tmpl \
		>./.github/workflows/branch-deploy-"${INSTANCE_NAME}".yaml

	# commit to git
	git add \
		./.dagster/dagster-cloud-"${INSTANCE_NAME}".yaml \
		./.github/workflows/deploy-"${INSTANCE_NAME}".yaml \
		./.github/workflows/branch-deploy-"${INSTANCE_NAME}".yaml
	git commit -m "Add ${INSTANCE_NAME} cloud workspace config"

	if [[ ! -d ./env/"${INSTANCE_NAME}" ]]; then
		# create local env dir
		mkdir -p ./env/"${INSTANCE_NAME}"

		# create local .env
		tmpfile=$(mktemp)
		cat ./env/core.env \
			./env/local.env.tmpl \
			>"${tmpfile}"
		envsubst <"${tmpfile}" >./env/"${INSTANCE_NAME}".env

		# create prod and stg .env
		pdm run env-update "${INSTANCE_NAME}"

		# create local branch
		git switch -c "${INSTANCE_NAME}"

		# configure local branch
		sed -i -e "s/dev/${INSTANCE_NAME}/g" ./pyproject.toml

		# commit to branch
		git add ./pyproject.toml
		git commit -m "Create ${INSTANCE_NAME} branch"
		git status
	fi
fi
