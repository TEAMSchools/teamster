# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

School-specific dbt project for **KIPP New Jersey - Camden** schools. Combines
local PowerSchool staging with cross-project references to produce school-level
extracts.

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

All materialized as tables via cross-project `ref()`:

- `powerschool` (ODBC) — `powerschool_external_location_root` points to GCS
- `deanslist`
- `edplan`
- `overgrad`
- `pearson`
- `titan`

Note: Camden does not use `iready` or `renlearn`.

## Key Variables

| Variable                             | Value                                                     |
| ------------------------------------ | --------------------------------------------------------- |
| `current_academic_year`              | `2025`                                                    |
| `current_fiscal_year`                | `2026`                                                    |
| `local_timezone`                     | `America/New_York`                                        |
| `cloud_storage_uri_base`             | `gs://teamster-kippcamden/dagster/kippcamden`             |
| `powerschool_external_location_root` | `gs://teamster-kippcamden/dagster/kippcamden/powerschool` |

## Model Conventions

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
