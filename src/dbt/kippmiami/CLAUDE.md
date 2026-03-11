# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

School-specific dbt project for **KIPP Miami** schools (Florida). The only
school project with Florida-specific state data (`fldoe`). Produces school-level
PowerSchool staging and extracts.

## Model Structure

```text
models/
  powerschool/   # school-specific PowerSchool staging (refs powerschool package)
    sis/staging/
  fldoe/         # Florida Department of Education assessment data
    staging/
  extracts/
    powerschool/ # PowerSchool autocomm extracts (teachers)
```

PowerSchool data source: **ODBC** (`odbc.+enabled: true`,
`sftp.+enabled: false`)

## Active Source Packages

All materialized as tables via cross-project `ref()`:

- `powerschool` (ODBC) — `powerschool_external_location_root` points to GCS
- `deanslist`
- `iready`
- `renlearn`

Note: Miami does not use `edplan`, `overgrad`, `pearson`, or `titan`.

## Key Variables

| Variable                             | Value                                                   |
| ------------------------------------ | ------------------------------------------------------- |
| `current_academic_year`              | `2025`                                                  |
| `current_fiscal_year`                | `2026`                                                  |
| `local_timezone`                     | `America/New_York`                                      |
| `cloud_storage_uri_base`             | `gs://teamster-kippmiami/dagster/kippmiami`             |
| `powerschool_external_location_root` | `gs://teamster-kippmiami/dagster/kippmiami/powerschool` |

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
      arguments:
        combination_of_columns:
          - column_a
          - column_b
      config:
        store_failures: true
```
