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

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
