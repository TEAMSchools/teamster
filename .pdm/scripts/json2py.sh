#!/bin/bash

IFS="." read -r -a input_array <<<"${1}"
input_file_type=${input_array[1]}

datamodel-codegen \
  --input "${1}" \
  --input-file-type "${input_file_type}" \
  --output "${input_array[0]}".py \
  --output-model-type pydantic_v2.BaseModel \
  --use-standard-collections \
  --force-optional
