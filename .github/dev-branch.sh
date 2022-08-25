#!/bin/bash

bash ./.github/pull-all.sh

for BRANCH in ./.git/refs/remotes/origin/kipp*; do
	branch_name=$(basename -- "${BRANCH}")

	git checkout -b merge-dev-"${branch_name}" "${branch_name}"
	git merge dev
	git push
done

git switch dev
