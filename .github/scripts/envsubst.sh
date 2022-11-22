#!/bin/bash

for tmpl_in in $(tree -af -I ".git|.trunk" --noreport -F -i); do

	if [[ -d ${tmpl_in} ]] && [[ ${tmpl_in} == "./src/.tmpl/" ]]; then
		echo "Processing src directory"
		mv src/.tmpl/ "src/${GITHUB_REPOSITORY_NAME}/"
	fi

	if [[ -f ${tmpl_in} ]] && [[ ${tmpl_in} =~ \.tmpl$ ]]; then
		tmpl_out=${tmpl_in%.*}

		echo "Processing file: ${tmpl_in} => ${tmpl_out}"
		envsubst <"${tmpl_in}" >"${tmpl_out}"

		rm "${tmpl_in}"
	fi

	if [[ ${tmpl_in} == "./README.md.tmpl" ]]; then
		echo "Copying file: README.md => docs/index.md"
		mkdir -p docs && cp README.md docs/index.md
	fi
done
