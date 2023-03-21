#!/bin/bash

file_envvars=(
  "DEANSLIST_API_KEY_MAP"
  "EGENCIA_RSA_PRIVATE_KEY"
  "GCLOUD_SERVICE_ACCOUNT_KEY"
  "DBT_USER_CREDS"
)

while read -ra array; do
  envvar="${array[0]}"
  envvar_lower="${envvar,,}"
  secret_name="${envvar_lower//_/-}"
  if [[ ! ${file_envvars[*]} =~ ${envvar} ]]; then
    kubectl create secret generic "${secret_name}" \
      --save-config \
      --dry-run=client \
      --namespace=dagster-cloud \
      --from-literal="${envvar}"="${!envvar}" \
      --output=yaml |
      kubectl apply -f - ||
      true
  fi
done < <(gh secret list --app codespaces || true)

kubectl create secret generic "secret-files" \
  --save-config \
  --dry-run=client \
  --namespace=dagster-cloud \
  --from-literal="id_rsa_egencia"="${EGENCIA_RSA_PRIVATE_KEY}" \
  --from-literal="dbt_user_creds_json"="${DBT_USER_CREDS}" \
  --from-literal="deanslist_api_key_map_json"="${DEANSLIST_API_KEY_MAP}" \
  --output=yaml |
  kubectl apply -f - ||
  true
