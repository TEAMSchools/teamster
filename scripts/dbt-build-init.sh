#!/bin/bash

run_project() {
  local project="$1"
  uv run scripts/dbt-sxs.py "${project}"
  uv run dbt build --full-refresh --project-dir="src/dbt/${project}/"
}

run_project kippcamden &
run_project kippmiami &
run_project kippnewark &
run_project kipppaterson &
wait

run_project kipptaf
