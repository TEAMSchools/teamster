#!/bin/bash

read -p "Enter instance name: " instance_name
export INSTANCE_NAME=$instance_name

# create local.env dir
mkdir -p ./env/${INSTANCE_NAME}

# create local.env
tmpfile=$(mktemp)
cat ./env/common.env \
    ./env/local.env.tmpl \
	> $tmpfile
envsubst < $tmpfile > ./env/${INSTANCE_NAME}/local.env

cp ./env/${INSTANCE_NAME}/local.env ./env/${INSTANCE_NAME}/prod.env
echo "
# deployment
DAGSTER_CLOUD_DEPLOYMENT=prod" >> ./env/${INSTANCE_NAME}/prod.env

cp ./env/${INSTANCE_NAME}/local.env ./env/${INSTANCE_NAME}/stg.env
echo "
# deployment
DAGSTER_CLOUD_DEPLOYMENT=stg" >> ./env/${INSTANCE_NAME}/stg.env
