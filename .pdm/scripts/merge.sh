#!/bin/bash

for branch in $(git for-each-ref --format='%(refname:short)' refs/**/origin/kipp*); do
  branch_name=$(basename -- "${branch}")

  git switch "${branch_name}"
  git pull

  if [[ ${1} == "hotfix" ]]; then
    git merge main
  elif [[ ${1} == "root" ]]; then
    git merge --no-ff --no-commit main
    git reset HEAD src/
    git checkout -- src/
    git commit -m "Merge project root"
  else
    git switch stg-"${branch_name}"
    git merge "${branch_name}"
    git merge main
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

git switch main
