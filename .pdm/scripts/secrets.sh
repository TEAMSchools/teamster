#!/bin/bash

# ignore envs
file_envvars=(
  "DEANSLIST_API_KEY_MAP"
  "EGENCIA_RSA_PRIVATE_KEY"
  "GCLOUD_SERVICE_ACCOUNT_KEY"
  "DBT_USER_CREDS"
)

# clear env file
: >env/.env

while read -ra array; do
  envvar="${array[0]}"

  if [[ ! ${file_envvars[*]} =~ ${envvar} ]]; then
    echo "${envvar}"="${!envvar}" >>env/.env
  fi
done < <(gh secret list --app codespaces || true)

while IFS="=" read -ra envvar || [[ -n ${envvar[*]} ]]; do
  envvar_lower="${envvar[0],,}"

  secret_name="${envvar_lower//_/-}"

  kubectl create secret generic "${secret_name}" \
    --save-config \
    --dry-run=client \
    --namespace=dagster-cloud \
    --from-literal="${envvar}"="${!envvar}" \
    --output=yaml |
    kubectl apply -f - ||
    true
done <env/.env

kubectl create secret generic "secret-files" \
  --save-config \
  --dry-run=client \
  --namespace=dagster-cloud \
  --from-literal="id_rsa_egencia"="${EGENCIA_RSA_PRIVATE_KEY}" \
  --from-literal="dbt_user_creds_json"="${DBT_USER_CREDS}" \
  --from-literal="deanslist_api_key_map_yaml"="${DEANSLIST_API_KEY_MAP}" \
  --from-literal="gcloud_service_account_json"="${GCLOUD_SERVICE_ACCOUNT_KEY}" \
  --output=yaml |
  kubectl apply -f - ||
  true
