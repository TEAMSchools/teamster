#!/bin/bash

branch=$(git branch --show-current)
branch_clean="${branch#stg-}"

if [[ -f "env/${branch_clean}/.env" ]]; then
  cp --remove-destination "env/${branch_clean}/.env" env/.env
else
  echo >env/.env
fi
