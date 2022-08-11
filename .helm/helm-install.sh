#!/bin/bash

helm repo add dagster-cloud https://dagster-io.github.io/helm-user-cloud
helm repo update

helm show values dagster-cloud/dagster-cloud-agent >./.helm/values.yaml

envsubst <./.helm/values-override.yaml.tmpl >./.helm/values-override.yaml

helm upgrade --install user-cloud dagster-cloud/dagster-cloud-agent \
	--namespace dagster-cloud \
	-f ./.helm/values-override.yaml
