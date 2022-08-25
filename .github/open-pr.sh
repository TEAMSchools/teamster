#!/bin/bash

for BRANCH in ./.git/refs/remotes/origin/stg-*; do
	branch_name=$(basename -- "${BRANCH}")

	git switch "${branch_name}"
	gh pr create --base "${branch_name#*-}"
done

git switch dev
