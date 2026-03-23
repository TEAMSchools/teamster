#!/bin/bash

set -euo pipefail

# Install kubectl and GKE auth plugin
gcloud components install kubectl gke-gcloud-auth-plugin --quiet

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

# Install gke-mcp
gke_mcp_dir="${HOME}/.local/bin"
mkdir -p "${gke_mcp_dir}"
curl --fail -L \
  https://github.com/GoogleCloudPlatform/gke-mcp/releases/download/v0.10.0/gke-mcp_Linux_x86_64.tar.gz \
  -o /tmp/gke-mcp.tar.gz ||
  {
    echo "❌ gke-mcp download failed"
    exit 1
  }
echo "93ade2e2fd73e767a9db407c4908e17871b54d222aebf570344f5a0535bd0868  /tmp/gke-mcp.tar.gz" |
  sha256sum -c - ||
  {
    echo "❌ gke-mcp checksum mismatch"
    exit 1
  }
tar --no-same-owner -xzf /tmp/gke-mcp.tar.gz -C /tmp gke-mcp
install -m 0755 /tmp/gke-mcp "${gke_mcp_dir}/"
rm /tmp/gke-mcp.tar.gz /tmp/gke-mcp

# Ensure namespace exists
kubectl create namespace dagster-cloud --dry-run=client -o yaml | kubectl apply -f -
