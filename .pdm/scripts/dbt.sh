#!/bin/bash

project="${1}"
dbt_command="${2}"
flags=("${@:3}")

if [[ ${dbt_command} == "sxs" ]]; then
  dbt run-operation --project-dir src/dbt/"${project}" \
    stage_external_sources \
    --vars "ext_full_refresh: true" \
    --args "select: ${flags[*]}"
else
  # trunk-ignore(shellcheck/SC2068)
  dbt "${dbt_command}" --project-dir src/dbt/"${project}" ${flags[@]}
fi
