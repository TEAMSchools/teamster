#!/bin/bash

# https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity#authenticating_to
# Get credentials for your cluster:
gcloud container clusters get-credentials autopilot-cluster-dagster-hybrid

# Create an IAM service account for your application
# or use an existing IAM service account instead.
gcloud iam service-accounts \
  create user-cloud-dagster-cloud-agent --project="teamster-332318"

# Ensure that your IAM service account has the roles you need.
# You can grant additional roles using the following command:
gcloud projects \
  add-iam-policy-binding "teamster-332318" \
  --member "serviceAccount:user-cloud-dagster-cloud-agent@teamster-332318.iam.gserviceaccount.com" \
  --role "roles/storage.admin"

# Allow the Kubernetes service account to impersonate the IAM service account
# by adding an IAM policy binding between the two service accounts.
# This binding allows the Kubernetes service account to act as the IAM service account.
gcloud iam service-accounts \
  add-iam-policy-binding "user-cloud-dagster-cloud-agent@teamster-332318.iam.gserviceaccount.com" \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:teamster-332318.svc.id.goog[dagster-cloud/user-cloud-dagster-cloud-agent]"

# Annotate the Kubernetes service account
# with the email address of the IAM service account.
kubectl annotate serviceaccount user-cloud-dagster-cloud-agent \
  --namespace dagster-cloud \
  "iam.gke.io/gcp-service-account=user-cloud-dagster-cloud-agent@teamster-332318.iam.gserviceaccount.com"

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
