#!/bin/bash

if [[ -z ${1} ]]; then
  echo "Location name is required"
  exit 1
else
  kubectl create secret generic "${1}" \
    --save-config \
    --dry-run=client \
    --namespace=dagster-cloud \
    --from-env-file="env/${1}/.env" \
    --output=yaml |
    kubectl apply -f -

  for folder in ./env/"${1}"/rsapk/*; do
    kubectl create secret generic "${1}-ssh-keys" \
      --save-config \
      --dry-run=client \
      --namespace=dagster-cloud \
      --from-file="egencia-privatekey=${folder}/rsa-private-key" \
      --output=yaml |
      kubectl apply -f -
  done
fi
