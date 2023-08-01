#!/bin/bash

dbt run-operation --project-dir src/dbt/"${1}" \
  stage_external_sources \
  --vars "ext_full_refresh: true" \
  --args "select: ${2}"
