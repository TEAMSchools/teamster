#!/bin/bash
if [[ -z ${1} ]]; then
	echo "Usage: ${0} <instance_name>"
	exit 1
else
	pdm run env-update "${1}"

	# trunk-ignore(shellcheck/SC2312)
	kubectl create secret generic "${1}" \
		--save-config \
		--dry-run=client \
		--namespace=dagster-cloud \
		--from-env-file=./env/"${1}"/prod.env \
		--output=yaml |
		kubectl apply -f -

	if [[ -d ./secrets/"${1}" ]]; then
		# trunk-ignore(shellcheck/SC2312)
		kubectl create secret generic "${1}"-ssh-keys \
			--save-config \
			--dry-run=client \
			--namespace=dagster-cloud \
			--from-file=egencia-privatekey=./secrets/"${1}"/egencia/rsa-private-key \
			--output=yaml |
			kubectl apply -f -
	fi
fi
