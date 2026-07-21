# CLAUDE.md — `dbt/kippmiami/`

District-specific dbt project for **KIPP Miami** schools (Florida). The only
district project with Florida-specific state data (`fldoe`). Produces
school-level PowerSchool staging and extracts.

## Model Structure

```text
models/
  fldoe/         # Florida Department of Education assessment data
    staging/
```

PowerSchool (pre-Focus SIS) is retired. The frozen `kippmiami_powerschool`
BigQuery dataset (source, not a dbt package) now feeds
`int_fldoe__all_assessments` directly; `powerschool` is no longer in
`packages.yml`.

## Source Packages

Package list: `packages.yml` is ground truth (see `src/dbt/CLAUDE.md`). `focus`
— `focus_schema` points to `dagster_kippmiami_dlt_focus`. Miami does not use
`edplan`, `overgrad`, `pearson`, `powerschool`, or `titan`.
