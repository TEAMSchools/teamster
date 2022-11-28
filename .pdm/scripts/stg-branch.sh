#!/bin/bash

for BRANCH in .git/refs/remotes/origin/kipp*; do
  branch_name=$(basename -- "${BRANCH}")

  git switch "${branch_name}"
  git pull

  git checkout -b stg-"${branch_name}" "${branch_name}"
  git merge dev
  git push
done

git switch dev
