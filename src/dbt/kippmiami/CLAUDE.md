# CLAUDE.md — `dbt/kippmiami/`

District-specific dbt project for **KIPP Miami** schools (Florida). The only
district project with Florida-specific state data (`fldoe`). Produces
school-level PowerSchool staging and extracts.

## Model Structure

```text
models/
  powerschool/   # district-specific PowerSchool staging (refs powerschool package)
    sis/staging/
  fldoe/         # Florida Department of Education assessment data
    staging/
  extracts/
    powerschool/ # PowerSchool autocomm extracts (teachers)
```

PowerSchool data source: **ODBC** (`odbc.+enabled: true`,
`sftp.+enabled: false`)

## Source Packages

Package list: `packages.yml` is ground truth (see `src/dbt/CLAUDE.md`). `focus`
— `focus_schema` points to `dagster_kippmiami_dlt_focus`. Miami does not use
`edplan`, `overgrad`, `pearson`, or `titan`.
