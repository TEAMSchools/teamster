#!/bin/bash

git switch dev

for BRANCH in ./teamster/kipp*/; do
	branch_name=$(basename -- "${BRANCH}")

	git merge "${branch_name}"
done
