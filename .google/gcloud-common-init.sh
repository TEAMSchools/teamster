#!/bin/bash

# https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity#authenticating_to
# Get credentials for your cluster:
gcloud container clusters get-credentials dagster-cloud

# Create an IAM service account for your application or use an existing IAM service account instead.
gcloud iam service-accounts \
  create user-cloud-dagster-cloud-agent --project="${GCP_PROJECT_ID}"

# Ensure that your IAM service account has the roles you need. You can grant additional roles using the following command:
gcloud projects \
  add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member "serviceAccount:user-cloud-dagster-cloud-agent@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role "roles/storage.admin"

# Allow the Kubernetes service account to impersonate the IAM service account by adding an IAM policy binding between the two service accounts.
# This binding allows the Kubernetes service account to act as the IAM service account.
gcloud iam service-accounts \
  add-iam-policy-binding user-cloud-dagster-cloud-agent@"${GCP_PROJECT_ID}".iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:${GCP_PROJECT_ID}.svc.id.goog[dagster-cloud/user-cloud-dagster-cloud-agent]"

# Annotate the Kubernetes service account with the email address of the IAM service account.
kubectl annotate serviceaccount user-cloud-dagster-cloud-agent \
  --namespace dagster-cloud \
  iam.gke.io/gcp-service-account=user-cloud-dagster-cloud-agent@"${GCP_PROJECT_ID}".iam.gserviceaccount.com

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
  --display-name="GitHub Provider" \
  --workload-identity-pool="github-pool" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository"

# save WI pool id to env
GH_WORKLOAD_IDENTITY_POOL_ID=gcloud iam workload-identity-pools describe "github-pool" \
  --project="${GCP_PROJECT_ID}" \
  --location="global" \
  --format="value(name)"

export GH_WORKLOAD_IDENTITY_POOL_ID=${GH_WORKLOAD_IDENTITY_POOL_ID}
echo "GH_WORKLOAD_IDENTITY_POOL_ID=${GH_WORKLOAD_IDENTITY_POOL_ID}" >>env/core.env
echo "GH_WORKLOAD_IDENTITY_POOL_PROVIDER=${GH_WORKLOAD_IDENTITY_POOL_ID}/providers/github-provider" >>env/core.env

# bind service account to WI pool
gcloud iam service-accounts \
  add-iam-policy-binding "${GCP_SERVICE_ACCOUNT}" \
  --project="${GCP_PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${GH_WORKLOAD_IDENTITY_POOL_ID}/attribute.repository/${GH_ORG_NAME}/teamster"

# create Artifact Registry repository
gcloud artifacts repositories create \
  teamster-core \
  --project="${GCP_PROJECT_ID}" \
  --location="${GCP_REGION}" \
  --repository-format=docker

# create Artifact Registry repository
gcloud artifacts repositories create \
  teamster-deps \
  --project="${GCP_PROJECT_ID}" \
  --location="${GCP_REGION}" \
  --repository-format=docker
