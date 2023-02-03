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

fi

# kubectl create secret generic "kipptaf-ssh-keys" \
#   --save-config \
#   --dry-run=client \
#   --namespace=dagster-cloud \
#   --from-file="egencia-privatekey=env/kipptaf/rsapk/egencia/rsa-private-key" \
#   --output=yaml |
#   kubectl apply -f -

# kubectl create secret generic "dbt-user-creds" \
#   --save-config \
#   --dry-run=client \
#   --namespace=dagster-cloud \
#   --from-file="dbt-user-creds=env/dbt-user-creds.json" \
#   --output=yaml |
#   kubectl apply -f -
