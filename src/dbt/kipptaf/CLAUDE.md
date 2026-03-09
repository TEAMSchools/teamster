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

**`extracts/powerschool/`** is a special case: `rpt_powerschool__autocomm_*`
models define a consistent export file format shared across all regions. They
are **not** extracted here — regional dbt projects (`kippnewark`, `kippcamden`,
`kippmiami`) each source from these models and filter to their own data, then
push to their respective PowerSchool instance. Therefore `extracts/powerschool/`
has no dbt exposure in kipptaf; exposures live in the regional projects.

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

## Exposures

Every external tool that consumes kipptaf data **must have a dbt exposure**
defined in `models/exposures/`. Exposures make the dependency graph explicit and
power Dagster asset lineage.

**All exposures** require:

```yaml
exposures:
  - name: exposure_name_snake_case
    label: Human Readable Title
    type: dashboard | application | analysis | notebook | ml
    owner:
      name: Data Team
    depends_on:
      - ref("rpt_tableau__some_model")
      - ref("rpt_gsheets__another_model")
    url: https://... # link to the external tool/workbook/sheet
    config:
      meta:
        dagster:
          kinds:
            - tableau # or: googlesheets, powerschool, etc.
```

**Tableau workbooks** may include the workbook LSID (`id`) under
`asset.metadata` to link the exposure to a specific Tableau Server workbook. Add
`cron_schedule` only when Dagster owns the refresh trigger:

```yaml
config:
  meta:
    dagster:
      kinds:
        - tableau
      asset:
        metadata:
          id: <tableau-workbook-lsid-uuid> # always include if known
          cron_schedule: "0 7 * * *" # only if Dagster manages the refresh
```

- `id` only → workbook is tracked in the asset graph but refreshed externally
- `id` + `cron_schedule` → Dagster owns the refresh schedule
- neither → workbook exposure with no asset-level metadata

Tableau workbooks with no metadata at all can omit the `asset` block entirely —
just the `kinds: [tableau]` is sufficient.

Exposure files live in `models/exposures/` grouped by tool: `tableau.yml`,
`google-sheets.yml`, `google-appsheet.yml`, etc.

## Legacy `base_` Prefix

Some models carry a `base_` prefix (e.g. `base_powerschool__*`). This is legacy
dbt guidance for lightweight join models that lived alongside `stg_` models in
the staging folder. **`base_` is considered outdated** — all `base_` models are
planned for renaming to `int_` (tracked in
[#2541](https://github.com/TEAMSchools/teamster/issues/2541)). Do not create new
`base_` models; use `int_` instead.

## Model Conventions

**All staging models must**:

1. Have `contract: enforced: true` (set at the directory level in
   `dbt_project.yml` or per-model in the properties YAML)
2. Have a uniqueness test — either a single-column `unique:` test or a
   multi-column `dbt_utils.unique_combination_of_columns` test

**All intermediate models must**:

1. Have a uniqueness test — either a single-column `unique:` test or a
   multi-column `dbt_utils.unique_combination_of_columns` test

**`rpt_` models** are analyst-built reporting views that serve as the data
source for external reporting tools (Tableau, Google Sheets, PowerSchool, etc.).
They live in `models/extracts/` and are distinct from the data mart layer.

**`dim_*` / `fct_*` models** are dimensional data mart models being built for
use with a semantic layer. They live in `models/marts/`. This layer is actively
being developed.

**All `rpt_` and `dim_*`/`fct_*` models must**:

1. Have `contract: enforced: true` — these are the last stop before data reaches
   an external reporting tool (Tableau, PowerSchool, Google Sheets, etc.).
   Schema changes break downstream exposures and must be made deliberately.
2. Have a uniqueness test — either a single-column `unique:` test or a
   multi-column `dbt_utils.unique_combination_of_columns` test:

```yaml
# single-column uniqueness
columns:
  - name: surrogate_key
    data_tests:
      - unique:
          config:
            store_failures: true

# multi-column uniqueness (when no single column is unique)
data_tests:
  - dbt_utils.unique_combination_of_columns:
      combination_of_columns:
        - column_a
        - column_b
      config:
        store_failures: true
```
