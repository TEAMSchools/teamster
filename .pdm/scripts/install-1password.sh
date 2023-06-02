#!/bin/bash

kubectl create secret generic onepassword-token \
  --save-config \
  --dry-run=client \
  --namespace=dagster-cloud \
  --from-literal=token="${OP_CONNECT_TOKEN}" \
  --output=yaml |
  kubectl apply -f - ||
  true

helm repo add 1password https://1password.github.io/connect-helm-charts/
helm repo update

helm show values 1password/connect >.helm/1password/values.yaml

helm upgrade \
  --install connect 1password/connect \
  --namespace dagster-cloud \
  --set-file connect.credentials=env/1password-credentials.json \
  -f .helm/1password/values-override.yaml
