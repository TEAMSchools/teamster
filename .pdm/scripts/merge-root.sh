#!/bin/bash

for BRANCH in .git/refs/remotes/origin/kipp*; do
  branch_name=$(basename -- "${BRANCH}")

  git switch "${branch_name}"
  git pull

  git merge --no-ff --no-commit dev
  git reset HEAD teamster/
  git checkout -- teamster/
  git commit -m "merged dev root"

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
