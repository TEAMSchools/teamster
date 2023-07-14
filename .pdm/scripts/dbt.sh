#!/bin/bash

dbt "${@:2}" --project-dir dbt/"${1}"
