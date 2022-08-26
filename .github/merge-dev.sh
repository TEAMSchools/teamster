#!/bin/bash

if [[ -z ${1} ]]; then
	echo "Usage: ${0} <deployment>"
	exit 1
else
	for BRANCH in ./.git/refs/remotes/origin/kipp*; do
		branch_name=$(basename -- "${BRANCH}")

		git switch "${1}"-"${branch_name}"
		git merge dev
	done

	git switch dev
fi
