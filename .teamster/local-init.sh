#!/bin/bash

read -r -p "Enter instance name: " instance_name

if [[ -z ${instance_name} ]]; then
	echo "<instance_name> is required"
	exit 1
else
	export INSTANCE_NAME=${instance_name}

	# create local.env dir
	mkdir -p ./env/"${INSTANCE_NAME}"

	# create local.env
	tmpfile=$(mktemp)
	cat ./env/common.env \
		./env/local.env.tmpl \
		>"${tmpfile}"
	envsubst <"${tmpfile}" >./env/"${INSTANCE_NAME}"/local.env

	# create prod and stg .env
	pdm run env-update "${INSTANCE_NAME}"
fi
