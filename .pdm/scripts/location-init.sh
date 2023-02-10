#!/bin/bash

read -r -p "Enter Code Location: " CODE_LOCATION
export LOCATION_NAME

if [[ -z ${CODE_LOCATION} ]]; then
  echo "<location_name> is required"
  exit 1
else
  # create local branch
  git switch -c "${CODE_LOCATION}"

  # create Dagster Cloud Code Location file
  envsubst \
    <.dagster/dagster-cloud.yaml.tmpl \
    >.dagster/dagster-cloud.yaml

  # commit to git
  git add .dagster/dagster-cloud.yaml
  git commit -m "Add ${CODE_LOCATION} cloud workspace config"

  # create Artifact Registry repository
  gcloud artifacts repositories create \
    "teamster-${CODE_LOCATION}" \
    --repository-format=docker

  # create GCS bucket
  gcloud storage buckets create "gs://teamster-${CODE_LOCATION}"

  # Push local env variables to k8s secret
  pdm run k8s-secret
fi
