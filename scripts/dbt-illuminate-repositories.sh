#!/bin/bash

sources=$(dbt list --project-dir src/dbt/kipptaf \
  --select source:illuminate.repository_* \
  --exclude source:illuminate.repository_fields source:illuminate.repository_grade_levels \
  --output json \
  --output-keys name)

while read -r line; do
  echo "${line}"
  model_name=$(echo "${line}" | jq -r .name)
  echo "{{ illuminate_repository_unpivot(model.name) }}" >"src/dbt/kipptaf/models/illuminate/staging/repositories/stg_illuminate__${model_name}.sql"
done <<<"${sources}"
