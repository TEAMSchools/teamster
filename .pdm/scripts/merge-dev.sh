#!/bin/bash

for BRANCH in .git/refs/remotes/heads/kipp*; do
  branch_name=$(basename -- "${BRANCH}")

  git switch "${branch_name}"
  git pull

  if [[ ${1} == "hotfix" ]]; then
    git merge dev
  elif [[ ${1} == "root" ]]; then
    git merge --no-ff --no-commit dev
    git reset HEAD src/
    git checkout -- src/
    git commit -m "Merge project root"
  else
    git switch stg-"${branch_name}"
    git merge "${branch_name}"
    git merge dev
  fi

  while true; do
    read -rp "Push (y/N)? " yn
    case ${yn} in
    [Yy]*)
      git push
      break
      ;;
    [Nn]*) break ;;
    *) break ;;
    esac
  done
done

git switch dev
