#!/bin/bash

# https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity#authenticating_to

# Get credentials for your cluster:
gcloud container clusters get-credentials dagster-cloud

# Create an IAM service account for your application or use an existing IAM service account instead.
gcloud iam service-accounts create user-cloud-dagster-cloud-agent --project="${GCP_PROJECT_ID}"

# Ensure that your IAM service account has the roles you need. You can grant additional roles using the following command:
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
	--member "serviceAccount:user-cloud-dagster-cloud-agent@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
	--role "roles/storage.admin"

# Allow the Kubernetes service account to impersonate the IAM service account by adding an IAM policy binding between the two service accounts.
# This binding allows the Kubernetes service account to act as the IAM service account.
gcloud iam service-accounts add-iam-policy-binding user-cloud-dagster-cloud-agent@"${GCP_PROJECT_ID}".iam.gserviceaccount.com \
	--role roles/iam.workloadIdentityUser \
	--member "serviceAccount:${GCP_PROJECT_ID}.svc.id.goog[dagster-cloud/user-cloud-dagster-cloud-agent]"

# Annotate the Kubernetes service account with the email address of the IAM service account.
kubectl annotate serviceaccount user-cloud-dagster-cloud-agent \
	--namespace dagster-cloud \
	iam.gke.io/gcp-service-account=user-cloud-dagster-cloud-agent@"${GCP_PROJECT_ID}".iam.gserviceaccount.com
