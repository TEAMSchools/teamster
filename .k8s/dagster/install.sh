#!/bin/bash

set -euo pipefail

# This is the deploy step only. .k8s/setup.sh provisions the prerequisites:
# the helm/kubectl toolchain, gcloud auth, cluster credentials, and the
# dagster-cloud namespace. Most failures below trace back to a missing one, so
# point back to setup.sh on any error (the clean "Aborted." exit 0 path skips
# this trap).
on_error() {
  status=$?
  echo "" >&2
  echo "install.sh failed (exit ${status})." >&2
  echo "Missing tool, unreachable cluster, or missing namespace? Run the" >&2
  echo "environment bootstrap first, then retry:" >&2
  echo "  bash .k8s/setup.sh" >&2
}
trap on_error ERR

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
