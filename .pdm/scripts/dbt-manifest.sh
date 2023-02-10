#!/bin/bash

if [[ -z ${1} ]]; then
  echo "Code Location is required"
  exit 1
else
  dbt deps --project-dir "teamster-dbt/${1}" --profiles-dir "teamster-dbt/${1}"
  dbt list --project-dir "teamster-dbt/${1}" --profiles-dir "teamster-dbt/${1}"
fi
