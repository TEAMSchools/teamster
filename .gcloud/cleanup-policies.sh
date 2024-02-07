#!/bin/bash

gcloud artifacts repositories set-cleanup-policies teamster \
  --project=teamster-332318 \
  --location=us-central1 \
  --policy=.gcloud/cleanup-policies.json \
  --no-dry-run
