# teamster 🚛

[![kipptaf](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kipptaf.yaml/badge.svg)](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kipptaf.yaml)
[![kippnewark](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippnewark.yaml/badge.svg)](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippnewark.yaml)
[![kippcamden](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippcamden.yaml/badge.svg)](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippcamden.yaml)
[![kippmiami](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippmiami.yaml/badge.svg)](https://github.com/TEAMSchools/teamster/actions/workflows/deploy-prod-kippmiami.yaml)

[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Trunk](https://img.shields.io/badge/trunk.io-enabled-brightgreen?logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGZpbGw9Im5vbmUiIHN0cm9rZT0iI0ZGRiIgc3Ryb2tlLXdpZHRoPSIxMSIgdmlld0JveD0iMCAwIDEwMSAxMDEiPjxwYXRoIGQ9Ik01MC41IDk1LjVhNDUgNDUgMCAxIDAtNDUtNDVtNDUtMzBhMzAgMzAgMCAwIDAtMzAgMzBtNDUgMGExNSAxNSAwIDAgMC0zMCAwIi8+PC9zdmc+)](https://trunk.io)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](CODE_OF_CONDUCT.md)

![Photograph taken in 1960. Upload from http://www.fortepan.hu/?lang=en&img=20566, part of Commons:Batch_uploading/Fortepan.HU](https://github.com/user-attachments/assets/2ca95e50-106c-4cce-a8e3-2ffb234adf94)

**Next-gen data orchestration for KIPP TEAM & Family Schools**

Teamster is the data engineering platform powering analytics and reporting
across KIPP Newark, Camden, Miami, and Paterson. It ingests data from 30+ source
systems, transforms it through dbt, and delivers it to Tableau, Google Sheets,
PowerSchool, and other consumers — all orchestrated by Dagster.

- 🎻 **Dagster** — orchestrates every ETL step across five code locations, one
  per school network;
  [observe and run pipelines in Dagster Cloud](https://kipptaf.dagster.cloud/)
- 🔧 **dbt** — transforms raw source data into staging, intermediate, mart, and
  extract models in **Google BigQuery**
- 🚿 **dlt** — loads data from API sources into BigQuery alongside dbt
- 🔀 **Airbyte** — managed connector pipelines for select integrations
- 🪣 **Google Cloud Storage** — intermediate storage layer between pipeline
  steps
- ☸️ **Google Kubernetes Engine** — runs each code location in its own container
  in production
- ⚙️ **GitHub Actions** — CI/CD for building and deploying code locations
- 📊 **Tableau** — primary BI consumer; Dagster manages workbook extract
  refreshes

## 📖 Background

KIPP's data infrastructure was previously a patchwork of Python scripts, cron
jobs, stored procedures, Fivetran, and Selenium automation spread across
multiple databases. Synchronous scheduling meant a slow pull from one system
would cascade into downstream failures. A single data engineer spent more time
firefighting than building.

Teamster replaced all of it with a unified, asset-based platform. The results:

- ⚡ Pipeline development time dropped from **weeks to days**
- 🎫 Data-related support tickets fell **30% year-over-year**
- 🧑‍💻 Analysts gained Git, SQL, and DevOps skills through shared PR workflows
- 🔔 Real-time Slack alerts replaced reactive debugging

> "The visibility into the pipelines is a game changer. We know as soon as
> something fails and why."

Read the full story in the
[Dagster case study](https://dagster.io/customers/kipp-case-study).

## 🚀 Get started

New to the project? Start here:

1. [Getting Started](getting-started.md) — account setup, Codespaces, local dev
2. [Architecture](reference/architecture.md) — how the code is organized
3. [Contributing](CONTRIBUTING.md) — workflow and PR guidelines

## 📚 Reference

| Topic                                                               | Description                                          |
| ------------------------------------------------------------------- | ---------------------------------------------------- |
| [Automations](reference/automations.md)                             | All schedules and sensors across every code location |
| [Automation Conditions](reference/automation-conditions.md)         | How asset auto-materialization works                 |
| [Adding an Integration](reference/adding-an-integration.md)         | Step-by-step guide for new data sources              |
| [dbt Conventions](reference/dbt-conventions.md)                     | Model naming, contracts, and testing standards       |
| [IO Managers](reference/io-managers.md)                             | How intermediate data is stored in GCS               |
| [Fiscal Year & Partitioning](reference/fiscal-year-partitioning.md) | Partition strategy for historical loads              |

## 🗺️ Guides & Troubleshooting

| Topic                                         | Description                              |
| --------------------------------------------- | ---------------------------------------- |
| [Dagster Guide](guides/dagster.md)            | Practical Dagster tips for this codebase |
| [dbt Guide](guides/dbt.md)                    | Practical dbt tips for this codebase     |
| [Troubleshooting](troubleshooting/dagster.md) | Common issues and fixes                  |
