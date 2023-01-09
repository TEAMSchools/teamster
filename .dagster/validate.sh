#!/bin/bash

if [[ -z ${1} ]]; then
  echo "location name is required"
  exit 1
else
  python -c "from teamster.${1}.definitions import defs"
fi
