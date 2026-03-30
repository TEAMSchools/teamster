# CLAUDE.md — `dbt/kippnewark/`

District-specific dbt project for **KIPP New Jersey - Newark** schools. Combines
local PowerSchool staging with cross-project references to produce school-level
extracts. This is the most complete NJ district project, including all available
source integrations.

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

All of the following are materialized as tables via cross-project `ref()`:

- `powerschool` (ODBC) — `powerschool_external_location_root` points to GCS
- `deanslist`
- `edplan`
- `iready` — uses `iready_schema: kippnj_iready`
- `overgrad`
- `pearson`
- `renlearn` — uses `renlearn_schema: kippnj_renlearn`
- `titan`

Several models from each package are disabled (see `dbt_project.yml`).
