#!/bin/bash

kubectl create namespace dagster-cloud

# https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity#authenticating_to

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

kubectl create secret generic dagster-cloud-agent-token \
  --save-config \
  --dry-run=client \
  --namespace=dagster-cloud \
  --from-literal=DAGSTER_CLOUD_AGENT_TOKEN="${DAGSTER_CLOUD_AGENT_TOKEN}" \
  --output=yaml |
  kubectl apply -f - ||
  true

bash .pdm/scripts/secrets.sh

helm repo add dagster-cloud https://dagster-io.github.io/helm-user-cloud
helm repo update

helm show values dagster-cloud/dagster-cloud-agent >.helm/dagster/values.yaml

helm upgrade \
  --install user-cloud dagster-cloud/dagster-cloud-agent \
  --namespace dagster-cloud \
  -f .helm/dagster/values-override.yaml
