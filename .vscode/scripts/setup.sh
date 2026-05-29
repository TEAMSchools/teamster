#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"

source "${SCRIPT_DIR}/shared/claude.sh"

# Wait for Claude Code extension to install on fresh rebuilds (up to ~1 min).
if [[ -z ${CLAUDE} ]]; then
  echo "⏳ Waiting for Claude Code extension to install..."
  _elapsed=0
  while [[ -z ${CLAUDE} && ${_elapsed} -lt 60 ]]; do
    sleep 5
    _elapsed=$((_elapsed + 5))
    CLAUDE=$(find ~/.vscode-remote/extensions/anthropic.claude-code-*/resources/native-binary/claude -type f 2>/dev/null | head -1) || true
  done
fi

if [[ -z ${CLAUDE} ]]; then
  echo -e "\033[1;33m⚠ Claude Code extension not found — install it and run the 'Claude: Login' task\033[0m"
elif "${CLAUDE}" auth status 2>/dev/null | grep -q '"loggedIn": true'; then
  echo -e "\033[1;32m✔ Claude authenticated\033[0m"
else
  bash "${SCRIPT_DIR}/claude-login.sh"
fi

if gcloud auth application-default print-access-token >/dev/null 2>&1; then
  echo -e "\033[1;32m✔ GCloud authenticated\033[0m"
else
  bash "${SCRIPT_DIR}/gcloud-application-default-login.sh"
fi

echo -e "\033[1;36mℹ Headless setup (GITHUB_USER, Claude plugins) handled by postStart.sh\033[0m"
echo -e "\033[1;36mℹ First time? Run 'dbt: Build Init' to populate dev datasets (Ctrl+Shift+P → Tasks: Run Task)\033[0m"
