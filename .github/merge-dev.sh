#!/bin/bash

if [[ -z ${1} ]]; then
	echo "Usage: ${0} <prod|stg>"
	exit 1
else
	for BRANCH in ./.git/refs/remotes/origin/kipp*; do
		branch_name=$(basename -- "${BRANCH}")

		git switch "${branch_name}"
		git pull

		if [[ ${1} == "stg" ]]; then
			git switch stg-"${branch_name}"
			git merge "${branch_name}"
		fi

		git merge dev

		echo "Push?"
		select yn in "Y" "N"; do
			case ${yn} in
			Y)
				git push
				break
				;;
			N) break ;;
			*) break ;;
			esac
		done
	done

	git switch dev
fi
