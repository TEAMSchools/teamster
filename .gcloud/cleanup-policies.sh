#!/bin/bash

declare -a code_locations=(
  "kippcamden"
  "kippnewark"
  "kippmiami"
  "kipptaf"
  "staging"
)

for i in "${code_locations[@]}"; do
  gcloud artifacts repositories set-cleanup-policies teamster-"${i}" \
    --project=teamster-332318 \
    --location=us-central1 \
    --policy=.gcloud/cleanup-policies-"${i}".json \
    --no-dry-run
done
