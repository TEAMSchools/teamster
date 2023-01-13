#!/bin/bash

if [[ -z ${1} ]]; then
  echo "Location name is required"
  exit 1
else
  set -o allexport
  # shellcheck source=/dev/null
  source env/"${1}"/.env
  python -c "from teamster.${1}.definitions import defs"
  set +o allexport
fi
