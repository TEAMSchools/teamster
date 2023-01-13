#!/bin/bash

if [[ -z ${1} ]]; then
  echo "Location name is required"
  exit 1
else
  if [[ -f "env/${1}/.env" ]]; then
    cp --remove-destination "env/${1}/.env" env/.env
  else
    echo >env/.env
  fi

  echo "${1}"
fi
