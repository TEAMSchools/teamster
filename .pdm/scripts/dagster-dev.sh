#!/bin/bash

if [[ -z ${1} ]]; then
  dagster dev \
    -m teamster.code_locations.kippcamden.definitions \
    -m teamster.code_locations.kippmiami.definitions \
    -m teamster.code_locations.kippnewark.definitions \
    -m teamster.code_locations.kipptaf.definitions
else
  dagster dev -m teamster.code_locations."${1}".definitions
fi
