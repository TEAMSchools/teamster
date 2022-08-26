#!/bin/bash

if [[ ${1} == "prod" ]]; then
	for BRANCH in ./.git/refs/remotes/origin/kipp*; do
		branch_name=$(basename -- "${BRANCH}")

		git switch "${branch_name}"
		git merge dev
	done

	git switch dev
elif [[ ${1} == "stg" ]]; then
	for BRANCH in ./.git/refs/remotes/origin/kipp*; do
		branch_name=$(basename -- "${BRANCH}")

		git switch "${branch_name}"
		git merge dev
	done

	git switch dev
else
	echo "Usage: ${0} <prod|stg>"
	exit 1
fi
