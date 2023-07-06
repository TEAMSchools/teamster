#!/bin/bash

dbt "${@:2}" --project-dir "${1}"
