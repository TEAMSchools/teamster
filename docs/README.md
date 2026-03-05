# teamster

[![kipptaf](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kipptaf.yaml/badge.svg)](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kipptaf.yaml)
[![kippnewark](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippnewark.yaml/badge.svg)](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippnewark.yaml)
[![kippcamden](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippcamden.yaml/badge.svg)](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippcamden.yaml)
[![kippmiami](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippmiami.yaml/badge.svg)](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippmiami.yaml)

[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Trunk](https://img.shields.io/badge/trunk.io-enabled-brightgreen?logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGZpbGw9Im5vbmUiIHN0cm9rZT0iI0ZGRiIgc3Ryb2tlLXdpZHRoPSIxMSIgdmlld0JveD0iMCAwIDEwMSAxMDEiPjxwYXRoIGQ9Ik01MC41IDk1LjVhNDUgNDUgMCAxIDAtNDUtNDVtNDUtMzBhMzAgMzAgMCAwIDAtMzAgMzBtNDUgMGExNSAxNSAwIDAgMC0zMCAwIi8+PC9zdmc+)](https://trunk.io)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](CODE_OF_CONDUCT.md)

![Photograph taken in 1960. Upload from http://www.fortepan.hu/?lang=en&img=20566, part of Commons:Batch_uploading/Fortepan.HU](https://github.com/user-attachments/assets/2ca95e50-106c-4cce-a8e3-2ffb234adf94)

Next-gen data orchestration for KIPP TEAM & Family Schools

## Overview

Teamster is a data engineering platform built on **Dagster** (orchestration),
**dbt** (transformations), and **Google BigQuery** (warehouse), with Google
Cloud Storage (GCS) as the intermediate storage layer.

All source code lives under `src/`:

- `src/teamster/` — Dagster project powering data orchestration
- `src/dbt/` — dbt projects organized by school network and data source

## Dagster

Dagster is our data orchestrator. Every ETL step runs here.

[Dagster Cloud](https://kipptaf.dagster.cloud/) is the hosted front-end where
you can observe and run integration jobs.

There is one code location per school network:

- `kipptaf` — network-wide (CMO); the largest code location
- `kippnewark`
- `kippcamden`
- `kippmiami`
- `kipppaterson`

Each code location runs in its own container on Google Cloud Kubernetes and owns
its jobs, schedules, sensors, and assets.

## dbt

dbt projects are organized as either school-network projects or shared
source-system projects:

- **School networks** (`kipptaf`, `kippnewark`, `kippcamden`, `kippmiami`,
  `kipppaterson`) — contain staging, intermediate, mart, and extract models.
  `kipptaf` is the primary analytics layer and the only project dbt Cloud is
  configured to run.
- **Source systems** (`powerschool`, `deanslist`, `iready`, etc.) — shared
  projects installed as dbt package dependencies across multiple school
  networks.

## Google Cloud Platform

- [Private GKE Autopilot](https://cloud.google.com/kubernetes-engine/docs/how-to/private-clusters#public_cp)
  cluster
- [Cloud NAT](https://cloud.google.com/nat/docs/gke-example#create-nat) for
  static external IP
- [Google Artifact Registry](https://cloud.google.com/artifact-registry/docs/docker/store-docker-container-images)
  for Docker images
- [Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity#authenticating_to)
  for Google Cloud service access
- GitHub Actions for CI/CD

## Airbyte

Airbyte is used for select data ingestion pipelines managed via the
`dagster-airbyte` integration.
