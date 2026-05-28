#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"

source "${SCRIPT_DIR}/shared/claude.sh"

# Wait for Claude Code extension to install on fresh rebuilds (up to ~1 min).
if [[ -z ${CLAUDE} ]]; then
  _elapsed=0
  while [[ -z ${CLAUDE} && ${_elapsed} -lt 60 ]]; do
    sleep 5
    _elapsed=$((_elapsed + 5))
    CLAUDE=$(find ~/.vscode-remote/extensions/anthropic.claude-code-*/resources/native-binary/claude -type f 2>/dev/null | head -1) || true
  done
fi

NEEDS_CLAUDE=0
NEEDS_GCLOUD=0

if [[ -n ${CLAUDE} ]] && ! "${CLAUDE}" auth status 2>/dev/null | grep -q '"loggedIn": true'; then
  NEEDS_CLAUDE=1
fi

if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  NEEDS_GCLOUD=1
fi

# Silent exit when nothing interactive is required — the headless work
# (GITHUB_USER cache, plugin sync, etc.) is handled by postStart.sh.
if [[ ${NEEDS_CLAUDE} -eq 0 && ${NEEDS_GCLOUD} -eq 0 ]]; then
  if [[ -z ${CLAUDE} ]]; then
    echo -e "\033[1;33m⚠ Claude Code extension not found — install it and run the 'Claude: Login' task\033[0m"
  fi
  exit 0
fi

[[ ${NEEDS_CLAUDE} -eq 1 ]] && bash "${SCRIPT_DIR}/claude-login.sh"
[[ ${NEEDS_GCLOUD} -eq 1 ]] && bash "${SCRIPT_DIR}/gcloud-application-default-login.sh"

echo -e "\033[1;36mℹ First time? Run 'dbt: Build Init' to populate dev datasets (Ctrl+Shift+P → Tasks: Run Task)\033[0m"
