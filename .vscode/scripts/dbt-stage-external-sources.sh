#!/bin/bash

set -euo pipefail

# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

PROJECT="${1:-all}"
TARGET="${2:-defer}"
SOURCE_SELECT="${3-}"

PROJECTS=(kippcamden kippmiami kippnewark kipppaterson kipptaf)

run_project() {
  local project="$1"
  local args=()
  if [[ -n ${SOURCE_SELECT} && ${SOURCE_SELECT} != "*" ]]; then
    args=(--args "{select: \"${SOURCE_SELECT}\"}")
  fi
  uv run dbt run-operation stage_external_sources \
    --project-dir "src/dbt/${project}/" \
    --target "${TARGET}" \
    --vars "{\"ext_full_refresh\": \"true\", \"cloud_storage_uri_base\": \"gs://teamster-${project}/dagster/${project}\"}" \
    "${args[@]}"
}

if [[ ${PROJECT} == "all" ]]; then
  for project in "${PROJECTS[@]}"; do
    run_project "${project}" &
  done
  wait
else
  run_project "${PROJECT}"
fi
