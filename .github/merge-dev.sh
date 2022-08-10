#!/bin/bash

for BRANCH in .git/refs/heads/*; do
	branch_name=$(basename -- "${BRANCH}")
	git switch "${branch_name}"
	git merge dev
done
