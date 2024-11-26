#!/bin/bash

project="${1}"
flags=("${@:3}")

dbt run-operation --project-dir src/dbt/"${project}" \
  stage_external_sources \
  --vars "ext_full_refresh: true" \
  --args "select: ${flags[*]}"
