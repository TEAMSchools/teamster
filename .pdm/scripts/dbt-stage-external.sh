#!/bin/bash

dbt run-operation --project-dir dbt/"${1}" \
  stage_external_sources \
  --vars "ext_full_refresh: true" \
  --args "select: ${2}"
