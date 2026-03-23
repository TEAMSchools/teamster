#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"

source "${SCRIPT_DIR}/shared/claude.sh"

if [[ -z ${GITHUB_USER-} ]]; then
  GITHUB_USER=$(gh api user --jq .login 2>/dev/null)
  export GITHUB_USER
  grep -q "export GITHUB_USER=" ~/.bashrc || echo "export GITHUB_USER=${GITHUB_USER}" >>~/.bashrc
fi

if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q .; then
  bash "${SCRIPT_DIR}/gcloud-application-default-login.sh"
else
  echo -e "\033[1;32m✔ GCloud authenticated\033[0m"
fi

if [[ -n ${CLAUDE} ]]; then
  if ! "${CLAUDE}" auth status 2>/dev/null | grep -q '"loggedIn": true'; then
    bash "${SCRIPT_DIR}/claude-login.sh"
  else
    echo -e "\033[1;32m✔ Claude authenticated\033[0m"
  fi

  PLUGINS_HASH=$(jq -c '{enabledPlugins, extraKnownMarketplaces}' .claude/settings.json | sha256sum | cut -d' ' -f1)
  HASH_FILE=~/.cache/teamster/claude_plugins_hash

  STORED_HASH=""
  if [[ -f ${HASH_FILE} ]]; then
    STORED_HASH=$(cat "${HASH_FILE}")
  fi

  if [[ ${STORED_HASH} != "${PLUGINS_HASH}" ]]; then
    bash "${SCRIPT_DIR}/claude-install-plugins.sh"
    mkdir -p ~/.cache/teamster && echo "${PLUGINS_HASH}" >"${HASH_FILE}"
  else
    echo -e "\033[1;32m✔ Claude plugins up to date\033[0m"

    INSTALLED=$(jq -r '.plugins | keys[]' ~/.claude/plugins/installed_plugins.json | sort)
    EXPECTED=$(jq -r '.enabledPlugins | keys[]' .claude/settings.json | sort)
    EXTRA=$(comm -23 <(echo "${INSTALLED}") <(echo "${EXPECTED}") || true)

    if [[ -n ${EXTRA} ]]; then
      echo -e "\033[1;36mℹ plugins installed but not in .claude/settings.json:\033[0m"
      echo "${EXTRA}" | while read -r plugin; do
        echo -e "\033[1;36m  - ${plugin}\033[0m"
      done
    fi
  fi
fi

bash "${SCRIPT_DIR}/check-dbt-dev-datasets.sh"
