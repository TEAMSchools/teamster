#!/bin/bash

# https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity#authenticating_to

# set up Workload Identity Federation for GitHub actions
# create WI pool
gcloud iam workload-identity-pools create "github-pool" \
  --project="teamster-332318" \
  --location="global" \
  --display-name="GitHub Pool"

# create WI provider for pool
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="teamster-332318" \
  --location="global" \
  --display-name="GitHub Provider" \
  --workload-identity-pool="github-pool" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository"

# bind service account to WI pool
GH_ORG_NAME=$(gh repo view --json owner --jq '.owner.login')

gcloud iam service-accounts \
  add-iam-policy-binding "service-account@teamster-332318.iam.gserviceaccount.com" \
  --project="teamster-332318" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/624231820004/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GH_ORG_NAME}/teamster"
