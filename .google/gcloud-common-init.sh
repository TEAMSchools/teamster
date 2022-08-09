#!/bin/bash

gcloud iam service-accounts add-iam-policy-binding "${GCP_SERVICE_ACCOUNT}" \
	--project="${GCP_PROJECT_ID}" \
	--role="roles/iam.workloadIdentityUser" \
	--member="principalSet://iam.googleapis.com/${GH_WORKLOAD_IDENTITY_POOL_ID}/attribute.repository/${GH_ORG_NAME}/teamster"
