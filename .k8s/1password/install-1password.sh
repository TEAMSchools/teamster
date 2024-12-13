#!/bin/bash

curl -fsSL -o .k8s/get_helm.sh \
  https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 &&
  chmod 700 .k8s/get_helm.sh &&
  .k8s/get_helm.sh

helm repo add 1password https://1password.github.io/connect-helm-charts/
helm repo update

helm show values 1password/connect >.k8s/1password/values.yaml

helm upgrade \
  --install connect 1password/connect \
  --set-file connect.credentials=1password-credentials.json \
  --set operator.token.value="${OP_CONNECT_TOKEN}" \
  --namespace dagster-cloud \
  -f .k8s/1password/values-override.yaml
