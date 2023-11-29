#!/bin/bash

# https://github.com/google-github-actions/auth/blob/main/README.md

export PROJECT_ID="teamster-332318"
export REPO="TEAMSchools/teamster" # e.g. "google/chrome"

### (Preferred) Direct Workload Identity Federation

# In this setup, the Workload Identity Pool has direct IAM permissions on Google
# Cloud resources; there are no intermediate service accounts or keys. This is
# preferred since it directly authenticates GitHub Actions to Google Cloud without
# a proxy resource. However, not all Google Cloud resources support `principalSet`
# identities. Please see the documentation for your Google Cloud service for more
# information.

# These instructions use the [gcloud][gcloud] command-line tool.

# 1.  Create a Workload Identity Pool:

gcloud iam workload-identity-pools create "github" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --display-name="GitHub Actions Pool"

# 2.  Get the full ID of the Workload Identity **Pool**:
# This value should be of the format:
# projects/123456789/locations/global/workloadIdentityPools/github

gcloud iam workload-identity-pools describe "github" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --format="value(name)"

export WORKLOAD_IDENTITY_POOL_ID=projects/624231820004/locations/global/workloadIdentityPools/github

# 3.  Create a Workload Identity **Provider** in that pool:

gcloud iam workload-identity-pools providers create-oidc teamster \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github" \
  --display-name="TEAMster Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# The attribute mappings map claims in the GitHub Actions JWT to assertions
# you can make about the request (like the repository or GitHub username of
# the principal invoking the GitHub Action). These can be used to further
# restrict the authentication using `--attribute-condition` flags.

# **❗️ NOTE!** You must map any claims in the incoming token to attributes
# before you can assert on those attributes in a CEL expression or IAM
# policy!**

# 4.  Extract the Workload Identity **Provider** resource name:

gcloud iam workload-identity-pools providers describe teamster \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github" \
  --format="value(name)"

# Use this value as the `workload_identity_provider` value in the GitHub
# Actions YAML:

# ```yaml
# - uses: 'google-github-actions/auth@v2'
#     with:
#     project_id: '${PROJECT_ID}'
#     workload_identity_provider: '...'
# "projects/123456789/locations/global/workloadIdentityPools/github/providers/${REPO}"
# ```
