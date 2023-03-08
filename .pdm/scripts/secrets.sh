#!/bin/bash

if [[ -z ${1} ]]; then
  echo "Code Location is required"
  exit 1
else
  kubectl create secret generic "${1}" \
    --save-config \
    --dry-run=client \
    --namespace=dagster-cloud \
    --from-env-file="env/${1}/.env" \
    --output=yaml |
    kubectl apply -f -

fi

# kubectl create secret generic "credential-files" \
#   --save-config \
#   --dry-run=client \
#   --namespace=dagster-cloud \
#   --from-file="egencia=env/kipptaf/rsapk/egencia/rsa-private-key" \
#   --from-file="dbt=env/dbt-user-creds.json" \
#   --output=yaml |
#   kubectl apply -f -
