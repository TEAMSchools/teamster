#!/bin/bash

# set up Workload Identity Federation for GitHub actions
# create WI pool
gcloud iam workload-identity-pools create "github-pool" \
	--project="${GCP_PROJECT_ID}" \
	--location="global" \
	--display-name="GitHub Pool"

# create WI provider for pool
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
	--project="${GCP_PROJECT_ID}" \
	--location="global" \
	--workload-identity-pool="github-pool" \
	--display-name="GitHub Provider" \
	--attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
	--issuer-uri="https://token.actions.githubusercontent.com"
