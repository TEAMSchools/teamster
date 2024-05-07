#!/bin/bash

if [[ -z ${1} ]]; then
  dagster dev \
    -m teamster.kippcamden.definitions \
    -m teamster.kippmiami.definitions \
    -m teamster.kippnewark.definitions \
    -m teamster.kipptaf.definitions
else
  dagster dev -m teamster."${1}".definitions
fi
