#!/usr/bin/env bash
# Setup script for Claude Code cloud sessions (claude.ai/code, mobile, routines).
#
# Paste this path into the cloud environment's "Setup script" field at
# https://claude.ai/settings/code-environments. It runs before Claude starts, so
# anything installed here is present when MCP servers and plugins load.
#
# It is idempotent: environment caching may replay it, and every step is a no-op
# when the work is already done.
#
# What it does NOT do: reach hosts the environment's egress policy denies. Add
# the hosts under "Allowed domains" on the environment first, or the dagster,
# dbt and tableau MCP servers stay down no matter what credentials you supply.

set -euo pipefail

log() { printf '[cloud-setup] %s\n' "$*"; }

# ---------------------------------------------------------------------------
# 1. Plugins
#
# Cloud sessions install plugins from .claude/settings.json "enabledPlugins",
# but only anthropics/claude-plugins-official gets its marketplace cloned
# automatically. The three third-party marketplaces have to be registered here
# or their plugins are silently missing for the whole session.
#
# Each marketplace's registered NAME comes from its own manifest, and an add is
# refused when that name is already declared in settings against a different
# repo. obra/superpowers-marketplace is the marketplace; obra/superpowers is one
# of the plugins inside it, which self-names "superpowers-dev".
# ---------------------------------------------------------------------------

add_marketplace() {
  local repo="$1"
  log "marketplace: ${repo}"
  claude plugin marketplace add "${repo}" 2>&1 | tail -1 || log "  (already present)"
}

install_plugin() {
  local plugin="$1"
  log "plugin: ${plugin}"
  claude plugin install "${plugin}" 2>&1 | tail -1 || log "  (already installed)"
}

add_marketplace "dagster-io/skills"
add_marketplace "dbt-labs/dbt-agent-skills"
add_marketplace "obra/superpowers-marketplace"

install_plugin "dagster-expert@dagster"
install_plugin "dbt@dbt-agent-marketplace"
install_plugin "superpowers@superpowers-marketplace"

# ---------------------------------------------------------------------------
# 2. gke-mcp binary
#
# .mcp.json calls "gke-mcp" off PATH. The devcontainer installs it; the cloud
# image does not. proxy.golang.org is on the default allowed-domain list, so
# this works without touching the egress policy.
# ---------------------------------------------------------------------------

if command -v gke-mcp >/dev/null 2>&1; then
  log "gke-mcp: already on PATH"
elif command -v go >/dev/null 2>&1; then
  log "gke-mcp: installing via go install"
  go install github.com/GoogleCloudPlatform/gke-mcp@latest || log "  install failed, gke MCP will not start"
  gopath="$(go env GOPATH)"
  export PATH="${PATH}:${gopath}/bin"
else
  log "gke-mcp: no go toolchain, skipping"
fi

# ---------------------------------------------------------------------------
# 3. Google application default credentials
#
# bigquery, gcp-observability and gke all read the ADC file named in .mcp.json.
# Cloud sessions have no gcloud login, so the key has to arrive as a variable
# set on the cloud environment.
#
# To enable: create a dedicated, least-privilege service account, base64 its
# JSON key, and set TEAMSTER_GCP_SA_KEY_B64 on the environment. Leave the
# variable unset and this block is skipped — those three servers simply stay
# down, exactly as they do today.
#
# Read the trade-off before you do this. A key in an environment variable is
# readable by every cloud session that uses this environment and by anything
# running inside the VM. Scope the service account to read-only access on the
# specific datasets and projects the MCP servers need, and nothing else.
# ---------------------------------------------------------------------------

adc_path="${HOME}/.config/gcloud/application_default_credentials.json"

if [[ -f "${adc_path}" ]]; then
  log "google credentials: already present"
elif [[ -n "${TEAMSTER_GCP_SA_KEY_B64:-}" ]]; then
  log "google credentials: writing from TEAMSTER_GCP_SA_KEY_B64"
  adc_dir="$(dirname "${adc_path}")"
  mkdir -p "${adc_dir}"
  printf '%s' "${TEAMSTER_GCP_SA_KEY_B64}" | base64 -d >"${adc_path}"
  chmod 600 "${adc_path}"
else
  log "google credentials: not configured, bigquery/gcp-observability/gke will not start"
fi

# ---------------------------------------------------------------------------
# 4. Launchers that fetch secrets from 1Password
#
# dagster, dbt and tableau all shell out to `op read`. Neither the 1Password CLI
# nor its download host is available in a cloud session, and dagster.cloud and
# us1.dbt.com are denied by the egress policy, so there is nothing this script
# can do for them yet. See docs for the two routes out of this.
# ---------------------------------------------------------------------------

log "dagster/dbt/tableau: need 1Password + allowed domains, see scripts/CLAUDE.md"

log "done"
