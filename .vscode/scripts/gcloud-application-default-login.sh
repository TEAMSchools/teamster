#!/bin/bash

set -euo pipefail

gcloud auth application-default login \
  --billing-project=teamster-332318 \
  --impersonate-service-account=codespaces@teamster-332318.iam.gserviceaccount.com \
  --scopes=https://www.googleapis.com/auth/bigquery,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/drive.metadata.readonly,https://www.googleapis.com/auth/iam.test,https://www.googleapis.com/auth/cloud-platform
