# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Source-system staging project for **PowerSchool SIS** data. Produces clean,
contract-enforced staging models consumed by all school-specific dbt projects
(`kippnewark`, `kippcamden`, `kippmiami`, `kipppaterson`) and `kipptaf`.

## Model Structure

```text
models/
  sis/
    base/        # base models (light renaming, no logic)
    staging/
      odbc/      # models sourced from live Oracle ODBC connection (enabled by default)
      sftp/      # models sourced from SFTP file extracts (disabled by default)
    intermediate/
```

All staging models have `contract: enforced: true`. Each school project
overrides `odbc.+enabled` and `sftp.+enabled` in its own `dbt_project.yml` to
select the ingestion method.

## Key Variables

| Variable                            | Default | Notes                                        |
| ----------------------------------- | ------- | -------------------------------------------- |
| `current_academic_year`             | `0`     | Overridden per school project                |
| `local_timezone`                    | `UTC`   | Overridden per school project                |
| `bigquery_external_connection_name` | `null`  | Set to BigLake connection in school projects |

## Cross-Project Usage

This project is never run standalone in production. School-specific projects
reference it as a dbt package and override variables and enabled flags. When a
school project runs, it resolves `ref('stg_powerschool__*')` models from this
project.

The `odbc/` vs `sftp/` split exists because some schools pull data via live
Oracle ODBC tunnel and others via SFTP file drops. Only one should be enabled
per deployment.

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
