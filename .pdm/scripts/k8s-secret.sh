#!/bin/bash

branch=$(git branch --show-current)

kubectl create secret generic "${branch}" \
  --save-config \
  --dry-run=client \
  --namespace=dagster-cloud \
  --from-env-file="env/${branch}/.env" \
  --output=yaml |
  kubectl apply -f -

if [[ -d "env/${branch}/keys" ]]; then
  kubectl create secret generic "${branch}-ssh-keys" \
    --save-config \
    --dry-run=client \
    --namespace=dagster-cloud \
    --from-file="egencia-privatekey=env/${branch}/keys/egencia/rsa-private-key" \
    --output=yaml |
    kubectl apply -f -
fi
