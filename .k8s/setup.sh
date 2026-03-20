#!/bin/bash

set -euo pipefail

# Install kubectl and GKE auth plugin
sudo gcloud components install kubectl gke-gcloud-auth-plugin --quiet

# Authenticate gcloud CLI (skips if already logged in)
if ! gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>/dev/null | grep -q .; then
  gcloud auth login
fi

# Discover and configure GKE cluster
cluster=$(
  gcloud container clusters list \
    --project=teamster-332318 \
    --format="value(name)" \
    --limit=1
)

region=$(
  gcloud container clusters list \
    --project=teamster-332318 \
    --format="value(location)" \
    --limit=1
)

gcloud container clusters get-credentials "${cluster}" \
  --project=teamster-332318 \
  --region="${region}"

# Install helm to user-local bin (avoids permission issues with /usr/local/bin)
helm_dir="${HOME}/.local/bin"
mkdir -p "${helm_dir}"
export PATH="${helm_dir}:${PATH}"
if [[ ! -x "${helm_dir}/helm" ]]; then
  curl -fsSL -o /tmp/get_helm.sh \
    https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
  chmod 700 /tmp/get_helm.sh
  USE_SUDO=false HELM_INSTALL_DIR="${helm_dir}" /tmp/get_helm.sh
  rm /tmp/get_helm.sh
fi

# Ensure namespace exists
kubectl create namespace dagster-cloud --dry-run=client -o yaml | kubectl apply -f -
