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

PowerSchool data source: **dlt** (Oracle over SSH tunnel → BigQuery;
`dlt.+enabled: true`, `odbc.+enabled: false`)

## Source Packages

Package list: `packages.yml` is ground truth (see `src/dbt/CLAUDE.md`).
District-specific notes:

- `iready` uses `iready_schema: kippnj_iready`; `renlearn` uses
  `renlearn_schema: kippnj_renlearn`
- `amplify` — products selectively enabled per `dbt_project.yml`
- Several models from each package are disabled (see `dbt_project.yml`)
