#!/bin/bash

set -euo pipefail

helm repo add dagster-cloud https://dagster-io.github.io/helm-user-cloud
helm repo update

helm show values dagster-cloud/dagster-cloud-agent >.k8s/dagster/values.yaml

echo "Running dry-run..."
helm upgrade \
  --install user-cloud dagster-cloud/dagster-cloud-agent \
  --namespace dagster-cloud \
  -f .k8s/dagster/values-override.yaml \
  --dry-run

read -r -p "Dry-run succeeded. Apply to cluster? [y/N] " response
if [[ ! ${response} =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

helm upgrade \
  --install user-cloud dagster-cloud/dagster-cloud-agent \
  --namespace dagster-cloud \
  -f .k8s/dagster/values-override.yaml

# ConfigMap changes don't trigger a rollout — force restart to pick up new env vars.
kubectl rollout restart deployment/user-cloud-dagster-cloud-agent-agent -n dagster-cloud
kubectl rollout status deployment/user-cloud-dagster-cloud-agent-agent -n dagster-cloud --timeout=600s
