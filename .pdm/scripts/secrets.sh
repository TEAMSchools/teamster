#!/bin/bash

file_envvars=(
  "DEANSLIST_API_KEY_MAP"
  "EGENCIA_RSA_PRIVATE_KEY"
  "GCLOUD_SERVICE_ACCOUNT_KEY"
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

# kubectl create secret generic "credential-files" \
#   --save-config \
#   --dry-run=client \
#   --namespace=dagster-cloud \
#   --from-file="egencia=env/kipptaf/rsapk/egencia/rsa-private-key" \
#   --from-file="dbt=env/dbt-user-creds.json" \
#   --output=yaml |
#   kubectl apply -f -
