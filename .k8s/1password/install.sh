#!/bin/bash

set -euo pipefail

helm repo add 1password https://1password.github.io/connect-helm-charts/
helm repo update

helm show values 1password/connect >.k8s/1password/values.yaml

source env/.env

echo "Running dry-run..."
helm upgrade \
  --install connect 1password/connect \
  --set-file connect.credentials=/etc/secret-volume/1password-credentials.json \
  --set operator.token.value="${OP_CONNECT_TOKEN}" \
  --namespace dagster-cloud \
  -f .k8s/1password/values-override.yaml \
  --dry-run

read -r -p "Dry-run succeeded. Apply to cluster? [y/N] " response
if [[ ! ${response} =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

helm upgrade \
  --install connect 1password/connect \
  --set-file connect.credentials=/etc/secret-volume/1password-credentials.json \
  --set operator.token.value="${OP_CONNECT_TOKEN}" \
  --namespace dagster-cloud \
  -f .k8s/1password/values-override.yaml
