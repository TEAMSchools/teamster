#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/shared/claude.sh"

if [[ -z ${CLAUDE} ]]; then
  echo 'ERROR: Claude Code extension binary not found. Is the extension installed?'
  exit 1
fi

if [[ ! -f ~/.cache/teamster/claude_auth_ok ]]; then
  echo 'ERROR: Not logged in to Claude. Run the "Claude: Login" task first.'
  exit 1
fi

SETTINGS='.claude/settings.json'

echo '--- Adding extra marketplaces ---'
jq -r '.extraKnownMarketplaces | to_entries[] | .value.source.repo' "${SETTINGS}" |
  while read -r repo; do
    "${CLAUDE}" plugins marketplace add "${repo}" --scope project || true
  done

echo '--- Installing plugins ---'
jq -r '.enabledPlugins | keys[]' "${SETTINGS}" |
  while read -r plugin; do
    "${CLAUDE}" plugins install "${plugin}" || true
  done

echo '--- Done ---'
