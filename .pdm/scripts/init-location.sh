#!/bin/bash

read -r -p "Enter location name: " LOCATION_NAME
read -r -p "Enter GCP Project ID: " GCP_PROJECT_ID
read -r -p "Enter GCP Region: " GCP_REGION

if [[ -z ${LOCATION_NAME} ]]; then
  echo "<location_name> is required"
  exit 1
else
  export LOCATION_NAME
  export GCP_PROJECT_ID
  export GCP_REGION

  # create DC location file
  envsubst \
    <.dagster/dagster-cloud.yaml.tmpl \
    >.dagster/dagster-cloud.yaml

  # commit to git
  git add .dagster/dagster-cloud.yaml
  git commit -m "Add ${LOCATION_NAME} cloud workspace config"

  # create local branch
  git switch -c "${LOCATION_NAME}"

  # commit to branch
  git add pyproject.toml
  git commit -m "Create ${LOCATION_NAME} branch"
  git status
fi
