#!/bin/bash

BRANCH=$(git branch --show-current)
declare BRANCH="${BRANCH^^}"

# varname=prefix_$suffix
echo "${!BRANCH}"
