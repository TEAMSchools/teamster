# CLAUDE.md — `dbt/kipppaterson/`

District-specific dbt project for **KIPP New Jersey - Paterson** schools. The
most limited district project — PowerSchool only, with a narrower set of enabled
models compared to Newark and Camden.

## Model Structure

```text
models/
  powerschool/   # district-specific PowerSchool staging (refs powerschool package)
    sis/staging/
```

PowerSchool data source: **SFTP** (`sftp.+enabled: true`,
`odbc.+enabled: false`)

This is the only NJ district using SFTP instead of ODBC for PowerSchool. Many
gradebook-related models (GPA, category grades, assignments) are explicitly
disabled.

## Active Source Packages

- `powerschool` (SFTP)
- `pearson` — all models currently disabled in `dbt_project.yml`
- `amplify` — both `dds` and `mclass/api` disabled
