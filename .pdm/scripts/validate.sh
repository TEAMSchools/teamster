#!/bin/bash

if [[ -z ${1} ]]; then
  echo "Code Location is required"
  exit 1
else
  dbt clean --project-dir dbt/"${1}" --profiles-dir dbt/"${1}" &&
    dbt deps --project-dir dbt/"${1}" --profiles-dir dbt/"${1}" &&
    dbt list --project-dir dbt/"${1}" --profiles-dir dbt/"${1}"

  python -m teamster."${1}".definitions
fi
