#!/bin/bash

if [[ -z ${1} ]]; then
  echo "Code Location is required"
  exit 1
else
  dbt clean --project-dir src/dbt/"${1}" --profiles-dir src/dbt/"${1}" &&
    dbt deps --project-dir src/dbt/"${1}" --profiles-dir src/dbt/"${1}" &&
    dbt list --project-dir src/dbt/"${1}" --profiles-dir src/dbt/"${1}"

  python -m teamster."${1}".definitions
fi
