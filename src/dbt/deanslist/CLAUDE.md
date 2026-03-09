# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Source-system staging project for **Deanslist** (behavior management, homework
tracking, and student support platform). Produces staging and intermediate
models consumed by school-specific projects and `kipptaf`.

## Model Structure

```text
models/
  staging/     # contract-enforced, one model per Deanslist API endpoint
  intermediate/
```

All staging models have `contract: enforced: true`. The
`bigquery_external_connection_name` var is `null` here and set by consuming
projects.

## Cross-Project Usage

Referenced as a dbt package by `kippnewark`, `kippcamden`, and `kipptaf`.
Consuming school projects may disable specific models (e.g.,
`stg_deanslist__followups`) in their own `dbt_project.yml`.

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
