# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

The **primary network-wide analytics project** for KIPP TEAM & Family (TAF).
This is the most complex dbt project — it aggregates data from all source-system
packages and all four school projects to produce network-level marts, reporting
models, and extracts for downstream tools (Tableau, PowerSchool, Deanslist,
Google Sheets, etc.).

## Model Structure

```text
models/
  <source>/          # one folder per integration (adp, deanslist, powerschool, etc.)
    staging/         # materialized: table, contract: enforced: true
    intermediate/
  assessments/       # cross-source assessment aggregations
  people/            # staff/HR unified layer
  students/          # cross-school student data
  marts/             # dim_* and fct_* models for Tableau (contract: enforced: true)
  reporting/         # topline reporting
  extracts/          # outbound feeds
    tableau/         # Tableau-specific extract models
    deanslist/
    powerschool/
    google/
    ...
  exposures/         # dbt exposures (Tableau, etc.)
```

## Key Architectural Notes

**Cross-project refs**: This project references all source-system packages
(`powerschool`, `deanslist`, `edplan`, `iready`, `overgrad`, `pearson`,
`renlearn`, `titan`, `amplify`, `finalsite`, `overgrad`) and resolves models
from those packages at run time. School-specific PowerSchool data is sourced
from multiple `sources-kipp*.yml` files.

**Marts layer** (`models/marts/`): Dimensional models (`dim_*`, `fct_*`) used by
Tableau. All have `contract: enforced: true`. Key models:

- `dim_students`, `dim_staff`, `dim_locations`, `dim_terms`, `dim_dates`,
  `dim_seats`
- `fct_attendance`, `fct_staff_attrition`, `fct_staff_terminations`,
  `fct_additional_earnings`, `fct_microgoals`

**People layer** (`models/people/`): Unified staff/HR view combining ADP, LDAP,
PowerSchool, and performance management data. Includes snapshots
(`snapshot_people__*`).

**Extracts layer** (`models/extracts/`): Outbound data feeds. Subdirectories map
to destination systems. All models have `contract: enforced: true`.

**Disabled integrations**: Several integrations are fully disabled at the
project level (ACT, ADP Workforce Manager, Alchemer, Dayforce, Facebook,
Instagram, ADP Payroll SFTP, Coupa Fivetran). See `dbt_project.yml`.

## Key Variables

| Variable                            | Value                                                                    |
| ----------------------------------- | ------------------------------------------------------------------------ |
| `current_academic_year`             | `2025`                                                                   |
| `current_fiscal_year`               | `2026`                                                                   |
| `local_timezone`                    | `America/New_York`                                                       |
| `cloud_storage_uri_base`            | `gs://teamster-kipptaf/dagster/kipptaf`                                  |
| `bigquery_external_connection_name` | `projects/teamster-332318/locations/us/connections/biglake-teamster-gcs` |

## dbt Cloud

This project is connected to dbt Cloud project ID `211862`. The `dbt-cloud`
block in `dbt_project.yml` enables dbt Cloud CI/CD.
