#!/bin/bash

project="${1}"
dbt_command="${2}"
flags=${*:3}

if [[ ${dbt_command} == "sxs" ]]; then
  dbt run-operation --project-dir src/dbt/"${project}" \
    stage_external_sources \
    --vars "ext_full_refresh: true" \
    --args "select: ${flags}"
else
  dbt "${dbt_command}" "${flags}" --project-dir src/dbt/"${project}"
fi
