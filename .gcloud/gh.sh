#!/bin/bash
# https://github.com/google-github-actions/auth?tab=readme-ov-file#preferred-direct-workload-identity-federation

gh_org_name=TEAMSchools
project_id=teamster-332318
project_number=624231820004
pool_name=github
repo=teamster
location=us-central1

# set up Workload Identity Federation for GitHub actions
# create WI pool
gcloud iam workload-identity-pools create \
  "${pool_name}" \
  --project="${project_id}" \
  --location="global" \
  --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools describe \
  "${pool_name}" \
  --project="${project_id}" \
  --location="global" \
  --format="value(name)"

# create WI provider for pool
gcloud iam workload-identity-pools providers create-oidc \
  "teamster" \
  --project="${project_id}" \
  --location="global" \
  --display-name="TEAMster Provider" \
  --workload-identity-pool="${pool_name}" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner == '${gh_org_name}'"

gcloud iam workload-identity-pools providers describe "teamster" \
  --project="${project_id}" \
  --location="global" \
  --workload-identity-pool="${pool_name}" \
  --format="value(name)"

# allow authentications from the Workload Identity Pool to Google Cloud resources
gcloud artifacts repositories add-iam-policy-binding \
  "${repo}" \
  --project="${project_id}" \
  --location="${location}" \
  --role="roles/artifactregistry.repoAdmin" \
  --member=principalSet://iam.googleapis.com/projects/"${project_number}"/locations/global/workloadIdentityPools/"${pool_name}"/attribute.repository/TEAMSchools/teamster
