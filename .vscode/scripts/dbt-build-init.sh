#!/bin/bash

set -euo pipefail

# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

PROJECT="${1:-all}"

run_project() {
  local project="$1"
  uv run scripts/dbt-sxs.py "${project}"
  uv run dbt build --full-refresh --project-dir="src/dbt/${project}/"
}

if [[ ${PROJECT} == "all" ]]; then
  # regional projects build in parallel; kipptaf depends on them and must follow
  run_project kippcamden &
  run_project kippmiami &
  run_project kippnewark &
  run_project kipppaterson &
  wait
  run_project kipptaf
else
  run_project "${PROJECT}"
fi
