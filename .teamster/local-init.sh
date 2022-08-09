#!/bin/bash

read -r -p "Enter instance name: " instance_name

if [[ -z ${instance_name} ]]; then
	echo "<instance_name> is required"
	exit 1
else
	export INSTANCE_NAME=${instance_name}

	# create local env dir
	mkdir -p ./env/"${INSTANCE_NAME}"

	# create local.env
	tmpfile=$(mktemp)
	cat ./env/common.env \
		./env/local.env.tmpl \
		>"${tmpfile}"
	envsubst <"${tmpfile}" >./env/"${INSTANCE_NAME}"/local.env

	# create prod and stg .env
	pdm run env-update "${INSTANCE_NAME}"

	# create GH worfklow files
	envsubst \
		<./.dagster/cloud-workspace-gh.yaml.tmpl \
		>./.dagster/"${INSTANCE_NAME}"-cloud-workspace-gh.yaml
	envsubst \
		<./.github/workflows/dagster-cloud-cicd.yaml.tmpl \
		>.github/workflows/"${INSTANCE_NAME}"-dagster-cloud-cicd.yaml
	git add \
		./.dagster/"${INSTANCE_NAME}"-cloud-workspace-gh.yaml \
		.github/workflows/"${INSTANCE_NAME}"-dagster-cloud-cicd.yaml
	git commit -m "Add ${INSTANCE_NAME} cloud workspace config"

	# create local branch
	git switch -c "${INSTANCE_NAME}"

	# configure local branch
	sed -i -e "s/core/${INSTANCE_NAME}/g" ./pyproject.toml
	echo "!teamster/${INSTANCE_NAME}/" >>./.dockerignore

	# commit to branch
	git add ./pyproject.toml ./.dockerignore
	git commit -m "Create local branch"

	# return to main
	git switch main
fi
