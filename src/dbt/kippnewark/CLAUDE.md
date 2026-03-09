# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

School-specific dbt project for **KIPP New Jersey - Newark** schools. Combines
local PowerSchool staging with cross-project references to produce school-level
extracts. This is the most complete NJ school project, including all available
source integrations.

## Model Structure

```text
models/
  powerschool/   # school-specific PowerSchool staging (refs powerschool package)
    sis/staging/
  edplan/        # refs edplan package
  extracts/
    powerschool/ # PowerSchool autocomm extracts (teachers, students IEP)
```

PowerSchool data source: **ODBC** (`odbc.+enabled: true`,
`sftp.+enabled: false`)

## Active Source Packages

All of the following are materialized as tables via cross-project `ref()`:

- `powerschool` (ODBC) — `powerschool_external_location_root` points to GCS
- `deanslist`
- `edplan`
- `iready` — uses `iready_schema: kippnj_iready`
- `overgrad`
- `pearson`
- `renlearn` — uses `renlearn_schema: kippnj_renlearn`
- `titan`

Several models from each package are disabled (see `dbt_project.yml`).

## Key Variables

| Variable                             | Value                                                     |
| ------------------------------------ | --------------------------------------------------------- |
| `current_academic_year`              | `2025`                                                    |
| `current_fiscal_year`                | `2026`                                                    |
| `local_timezone`                     | `America/New_York`                                        |
| `cloud_storage_uri_base`             | `gs://teamster-kippnewark/dagster/kippnewark`             |
| `powerschool_external_location_root` | `gs://teamster-kippnewark/dagster/kippnewark/powerschool` |
| `iready_schema`                      | `kippnj_iready`                                           |
| `renlearn_schema`                    | `kippnj_renlearn`                                         |

## Model Conventions

**All staging models must**:

1. Have `contract: enforced: true` (set at the directory level in
   `dbt_project.yml` or per-model in the properties YAML)
2. Have a uniqueness test — either a single-column `unique:` test or a
   multi-column `dbt_utils.unique_combination_of_columns` test

**All intermediate models must**:

1. Have a uniqueness test — either a single-column `unique:` test or a
   multi-column `dbt_utils.unique_combination_of_columns` test

**All extracts/marts models must**:

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
