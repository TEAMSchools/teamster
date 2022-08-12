#!/bin/bash

if [[ -z ${1} ]]; then
	echo "Usage: ${0} <instance_name>"
	exit 1
else
	cp ./env/"${1}"/local.env ./env/"${1}"/prod.env
	echo "
# deployment
DAGSTER_CLOUD_DEPLOYMENT=prod" >>./env/"${1}"/prod.env

	cp ./env/"${1}"/local.env ./env/"${1}"/docker.env
	echo "
# deployment
DAGSTER_CLOUD_DEPLOYMENT=docker" >>./env/"${1}"/docker.env
fi
