# teamster

[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)
[![Trunk](https://img.shields.io/badge/trunk.io-enabled-brightgreen?logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGZpbGw9Im5vbmUiIHN0cm9rZT0iI0ZGRiIgc3Ryb2tlLXdpZHRoPSIxMSIgdmlld0JveD0iMCAwIDEwMSAxMDEiPjxwYXRoIGQ9Ik01MC41IDk1LjVhNDUgNDUgMCAxIDAtNDUtNDVtNDUtMzBhMzAgMzAgMCAwIDAtMzAgMzBtNDUgMGExNSAxNSAwIDAgMC0zMCAwIi8+PC9zdmc+)](https://trunk.io)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](CODE_OF_CONDUCT.md)

![Photograph taken in 1960. Upload from http://www.fortepan.hu/?lang=en&img=20566, part of Commons:Batch_uploading/Fortepan.HU
](https://upload.wikimedia.org/wikipedia/commons/e/e4/Chariot%2C_donkey%2C_coach%2C_dirt_road%2C_barrel%2C_hat%2C_teamster%2C_man%2C_garden%2C_village_Fortepan_20566.jpg)

## About

### Dagster

Dagster is our data orchestrator. Every ETL step takes place here.

[Dagster Cloud](https://kipptaf.dagster.cloud/) is a hosted front-end for our Dagster servers where
you can observe and run integration jobs.

Dagster hosts multiple "code locations", one for each of our business units, including a separate
one for our CMO:

- kippnewark
- kippcamden
- kippmiami
- kipptaf

Each code location hosts and runs the code and configurations for each respective business unit.
Behind-the-scenes, these are containers run on Google Cloud Kubernetes. Each code location has it's
own respective jobs, schedules, sensors, and assets.

### dbt & Github

Before you merge:

1. Ensure dbt build runs successfully on your branch
2. Format your SQL changes in dbt
3. Ensure the Dagster build action runs successfully

### Google Cloud Platform

### Fivetran & Airbyte
