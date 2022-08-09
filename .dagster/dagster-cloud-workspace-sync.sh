#!/bin/bash

envsubst \
	< ./.dagster/cloud-workspace-"$1".yaml.tmpl \
	> ./.dagster/cloud-workspace-"$1".yaml

if [[ $1 == prod ]]; then
	pdm run k8s-secret
fi

dagster-cloud workspace sync \
	-d "$1" \
	-w ./.dagster/cloud-workspace-"$1".yaml
