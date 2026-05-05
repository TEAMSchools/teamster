#!/bin/bash

set -euo pipefail

# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

PROJECT="${1:-all}"

run_project() {
  local project="$1"
  uv run dbt clone --full-refresh \
    --project-dir="src/dbt/${project}/" \
    --state target/prod
}

if [[ ${PROJECT} == "all" ]]; then
  # regional projects build in parallel; kipptaf depends on them and must follow
  run_project kippcamden &
  run_project kippmiami &
  run_project kippnewark &
  run_project kipppaterson &
  run_project kipptaf &
  wait
else
  run_project "${PROJECT}"
fi
