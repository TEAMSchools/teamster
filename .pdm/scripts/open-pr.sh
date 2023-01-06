#!/bin/bash

for branch in $(git for-each-ref --format='%(refname:short)' refs/**/origin/stg-kipp*); do
  branch_name=$(basename -- "${branch}")

  git switch "${branch_name}"
  gh pr create --base "${branch_name#*-}"
done

git switch main
