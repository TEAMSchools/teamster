#!/bin/bash

if [[ -z ${1} ]]; then
	echo "Code Location is required"
	exit 1
else
	dbt deps --project-dir "${1}" --profiles-dir "${1}" &&
		dbt list --project-dir "${1}" --profiles-dir "${1}"
fi
