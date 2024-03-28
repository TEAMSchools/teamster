#!/bin/bash

project="${1}"
dbt_command="${2}"
flags=${*:3}

if [[ ${dbt_command} == "sxs" ]]; then
  dbt run-operation --project-dir src/dbt/"${project}" \
    stage_external_sources \
    --vars "ext_full_refresh: true" \
    --args "select: ${flags}"
elif [[ ${dbt_command} == "deps" ]]; then
  dbt "${dbt_command}" --project-dir src/dbt/"${project}"
elif [[ ${dbt_command} == "parse" ]]; then
  dbt "${dbt_command}" --project-dir src/dbt/"${project}"
elif [[ ${dbt_command} == "compile" ]]; then
  dbt "${dbt_command}" --project-dir src/dbt/"${project}"
else
  echo dbt "${dbt_command}" --project-dir src/dbt/"${project}" "${flags}"
  dbt "${dbt_command}" --project-dir src/dbt/"${project}" "${flags}"
fi
