---
name: gcloud-project-ops
description:
  "Use before any gcloud write (projects create, services enable, builds submit)
  or when gcloud returns 429 quota errors or Cloud Build cannot push an image:
  quota/billing project flags and Cloud Build service-account prerequisites."
---

# gcloud-project-ops

- **gcloud quota project**: Fresh `gcloud` writes (`projects create`,
  service-enable, etc.) hit 429 on Google's shared default project
  (`32555940559`) when no quota project is set. Pass
  `--billing-project=teamster-332318` per-command, or
  `gcloud config set billing/quota_project teamster-332318` once.
  `gcloud auth application-default set-quota-project` fails when ADC is a
  service-account credential — use the gcloud config form instead.

- **Cloud Build prereqs**: `gcloud builds submit` requires
  `cloudbuild.googleapis.com` enabled, and the Cloud Build SA
  (`<PROJECT_NUMBER>@cloudbuild.gserviceaccount.com`) needs
  `roles/artifactregistry.writer` on the target project to push the built image.
