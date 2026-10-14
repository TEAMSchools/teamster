#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/shared/claude.sh"

if [[ -z ${CLAUDE} ]]; then
	echo 'ERROR: Claude Code extension binary not found. Is the extension installed?'
	exit 1
fi

SETTINGS='.claude/settings.json'

# Read-only on ${SETTINGS}: --scope project rewrites its entries (dropping
# fields like autoUpdate), and postStart.sh re-runs this script on any change
# to them. User and local scopes write outside the tracked file.
echo '--- Adding extra marketplaces ---'
jq -r '.extraKnownMarketplaces | to_entries[] | .value.source.repo' "${SETTINGS}" |
	while read -r repo; do
		"${CLAUDE}" plugins marketplace add "${repo}" || true
	done

echo '--- Installing plugins ---'
jq -r '.enabledPlugins | keys[]' "${SETTINGS}" |
	while read -r plugin; do
		"${CLAUDE}" plugins install "${plugin}" --scope local || true
	done

echo '--- Done ---'
