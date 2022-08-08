#!/bin/bash

if [[ -z $1 ]]; then
	:
else
	tmpfile=$(mktemp)
	cat ./env/${INSTANCE_NAME}/.env ./env/"$1".env.tmpl > $tmpfile
	envsubst < $tmpfile > ./env/${INSTANCE_NAME}/"$1".env
fi
