#!/bin/bash

curl -fsSL -o .k8s/get_helm.sh \
  https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 &&
  chmod 700 .k8s/get_helm.sh &&
  .k8s/get_helm.sh

helm repo add dagster-cloud https://dagster-io.github.io/helm-user-cloud
helm repo update

helm show values dagster-cloud/dagster-cloud-agent >.k8s/dagster/values.yaml

helm upgrade \
  --install user-cloud dagster-cloud/dagster-cloud-agent \
  --namespace dagster-cloud \
  -f .k8s/dagster/values-override.yaml \
  --skip-schema-validation
