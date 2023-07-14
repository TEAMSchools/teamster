#!/bin/bash

dbt "${@:2}" --project-dir src/dbt/"${1}"
