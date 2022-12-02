#!/bin/bash

branch=$(git branch --show-current)

if [[ -f "env/${branch}/.env" ]]; then
  cp --remove-destination "env/${branch}/.env" env/.env
else
  echo >env/.env
fi
