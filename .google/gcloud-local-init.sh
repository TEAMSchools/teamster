#!/bin/bash

# create Artifact Registry repository
gcloud artifacts repositories create \
	"${IMAGE_NAME}" \
	--location="${GCP_REGION}" \
	--repository-format=docker

# create Storage bucket
gsutil mb -p "${GCP_PROJECT_ID}" gs://"${IMAGE_NAME}"

# Push local env variables to k8s secret
pdm run k8s-secret
