#!/bin/bash

for BRANCH in ./.git/refs/remotes/origin/kipp*; do
	branch_name=$(basename -- "${BRANCH}")

	git switch "${branch_name}"
	git pull
done

git switch dev
