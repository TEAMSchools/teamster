#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/shared/claude.sh"

if [[ -z ${CLAUDE} ]]; then
  echo 'ERROR: Claude Code extension binary not found. Is the extension installed?'
  exit 1
fi

"${CLAUDE}" auth login
