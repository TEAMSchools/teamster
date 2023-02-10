#!/bin/bash

if [[ -z ${1} ]]; then
  echo "Code Location is required"
  exit 1
else
  set -o allexport
  # shellcheck source=/dev/null
  source "env/${1}/.env"
  python -m "teamster.${1}.definitions"
  set +o allexport
fi
