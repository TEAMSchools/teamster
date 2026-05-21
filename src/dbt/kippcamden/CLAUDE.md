# CLAUDE.md — `dbt/kippcamden/`

District-specific dbt project for **KIPP New Jersey - Camden** schools. Combines
local PowerSchool staging with cross-project references to produce school-level
extracts.

## Model Structure

```text
models/
  powerschool/   # district-specific PowerSchool staging (refs powerschool package)
    sis/staging/
  edplan/        # refs edplan package
  extracts/
    powerschool/ # PowerSchool autocomm extracts (teachers, students IEP)
```

PowerSchool data source: **ODBC** (`odbc.+enabled: true`,
`sftp.+enabled: false`)

## Active Source Packages

All materialized as tables via cross-project `ref()`:

- `powerschool` (ODBC)
- `deanslist`
- `edplan`
- `overgrad`
- `pearson`
- `titan`

Note: Camden does not use `iready` or `renlearn`.
