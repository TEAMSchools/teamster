# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

School-specific dbt project for **KIPP New Jersey - Paterson** schools. The most
limited school project — PowerSchool only, with a narrower set of enabled models
compared to Newark and Camden.

## Model Structure

```text
models/
  powerschool/   # school-specific PowerSchool staging (refs powerschool package)
    sis/staging/
```

PowerSchool data source: **SFTP** (`sftp.+enabled: true`,
`odbc.+enabled: false`)

This is the only NJ school using SFTP instead of ODBC for PowerSchool. Many
gradebook-related models (GPA, category grades, assignments) are explicitly
disabled.

## Active Source Packages

- `powerschool` (SFTP)
- `pearson` — all models currently disabled in `dbt_project.yml`
- `amplify` — both `dds` and `mclass/api` disabled

## Key Variables

| Variable                 | Value                                             |
| ------------------------ | ------------------------------------------------- |
| `current_academic_year`  | `2025`                                            |
| `current_fiscal_year`    | `2026`                                            |
| `local_timezone`         | `America/New_York`                                |
| `cloud_storage_uri_base` | `gs://teamster-kipppaterson/dagster/kipppaterson` |

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
