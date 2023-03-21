#!/bin/bash

if [[ -z ${1} ]]; then
  echo "Code Location is required"
  exit 1
else
  python -m "teamster.${1}.definitions"
fi
