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

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
