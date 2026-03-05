# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Source-system staging project for **Amplify** reading assessments. Covers two
product lines with different ingestion paths:

- `dds/` — Amplify DDS (SFTP file drops)
- `mclass/api/` — mClass API data
- `mclass/sftp/` — mClass SFTP file drops

## Model Structure

```text
models/
  dds/
    staging/
  mclass/
    api/
      staging/
    sftp/
      staging/
  sources.yml
```

All staging models have `contract: enforced: true`. Both `dds` and `mclass/api`
can be independently enabled/disabled per school in the consuming project's
`dbt_project.yml`.

## Cross-Project Usage

Referenced by `kippnewark`, `kipppaterson`, and `kipptaf`. School projects
selectively enable only the Amplify products they use — for example,
`kipppaterson` disables both `dds` and `mclass/api`.

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
