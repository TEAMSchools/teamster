#!/bin/bash

for BRANCH in ./.git/refs/remotes/origin/kipp*; do
	branch_name=$(basename -- "${BRANCH}")

	git switch merge-dev-"${branch_name}"
	git merge dev
done

git switch dev
