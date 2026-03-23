#!/bin/bash

set -euo pipefail

# Install kubectl and gke-gcloud-auth-plugin as user-local binaries
# (gcloud components install and apt both require elevated privileges unavailable here)
tools_dir="${HOME}/.local/bin"
mkdir -p "${tools_dir}"
export PATH="${tools_dir}:${PATH}"

if [[ ! -x "${tools_dir}/kubectl" ]]; then
  kubectl_version=$(curl -fsSL https://dl.k8s.io/release/stable.txt)
  curl --fail -L \
    "https://dl.k8s.io/release/${kubectl_version}/bin/linux/amd64/kubectl" \
    -o /tmp/kubectl ||
    {
      echo "❌ kubectl download failed"
      exit 1
    }
  curl --fail -L \
    "https://dl.k8s.io/release/${kubectl_version}/bin/linux/amd64/kubectl.sha256" \
    -o /tmp/kubectl.sha256 ||
    {
      echo "❌ kubectl checksum download failed"
      exit 1
    }
  kubectl_sha=$(cat /tmp/kubectl.sha256)
  echo "${kubectl_sha}  /tmp/kubectl" | sha256sum -c - ||
    {
      echo "❌ kubectl checksum mismatch"
      exit 1
    }
  install -m 0755 /tmp/kubectl "${tools_dir}/kubectl"
  rm /tmp/kubectl /tmp/kubectl.sha256
fi

if [[ ! -x "${tools_dir}/gke-gcloud-auth-plugin" ]]; then
  sdk_cfg=/usr/local/share/google-cloud-sdk/lib/googlecloudsdk/core/config.json
  plugin_info=$(
    python3 - "${sdk_cfg}" <<'PYEOF'
import json, sys, urllib.request
cfg = json.load(open(sys.argv[1]))
snapshot_url = cfg["snapshot_url"]
base = snapshot_url.rsplit("/", 1)[0] + "/"
with urllib.request.urlopen(snapshot_url) as r:
    data = json.load(r)
for comp in data.get("components", []):
    if comp.get("id") == "gke-gcloud-auth-plugin-linux-x86_64":
        print(base + comp["data"]["source"], comp["data"]["checksum"])
        break
PYEOF
  )
  plugin_url="${plugin_info%% *}"
  plugin_checksum="${plugin_info##* }"
  curl --fail -L "${plugin_url}" -o /tmp/gke-gcloud-auth-plugin.tar.gz ||
    {
      echo "❌ gke-gcloud-auth-plugin download failed"
      exit 1
    }
  echo "${plugin_checksum}  /tmp/gke-gcloud-auth-plugin.tar.gz" | sha256sum -c - ||
    {
      echo "❌ gke-gcloud-auth-plugin checksum mismatch"
      exit 1
    }
  tar --no-same-owner -xzf /tmp/gke-gcloud-auth-plugin.tar.gz -C /tmp bin/gke-gcloud-auth-plugin
  install -m 0755 /tmp/bin/gke-gcloud-auth-plugin "${tools_dir}/"
  rm -rf /tmp/gke-gcloud-auth-plugin.tar.gz /tmp/bin
fi

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
