#!/bin/bash

read -r -p "Enter location name: " LOCATION_NAME
export LOCATION_NAME

if [[ -z ${LOCATION_NAME} ]]; then
  echo "<location_name> is required"
  exit 1
else
  # create local branch
  git switch -c "${LOCATION_NAME}"

  # create Dagster Cloud Code Location file
  envsubst \
    <.dagster/dagster-cloud.yaml.tmpl \
    >.dagster/dagster-cloud.yaml

  # commit to git
  git add .dagster/dagster-cloud.yaml
  git commit -m "Add ${LOCATION_NAME} cloud workspace config"

  # create Artifact Registry repository
  gcloud artifacts repositories create \
    "teamster-${LOCATION_NAME}" \
    --repository-format=docker

  # create GCS bucket
  gcloud storage buckets create "gs://teamster-${LOCATION_NAME}"

  # Push local env variables to k8s secret
  pdm run k8s-secret
fi
