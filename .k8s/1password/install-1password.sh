#!/bin/bash

helm repo add 1password https://1password.github.io/connect-helm-charts/
helm repo update

helm show values 1password/connect >.k8s/1password/values.yaml

helm upgrade \
  --install connect 1password/connect \
  --set-file connect.credentials=/etc/secret-volume/op_credentials_json \
  --set operator.token.value="${OP_CONNECT_TOKEN}" \
  --namespace dagster-cloud \
  -f .k8s/1password/values-override.yaml
