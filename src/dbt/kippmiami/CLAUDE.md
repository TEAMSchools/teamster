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

PowerSchool (pre-Focus SIS) is retired. `kippmiami_powerschool` is an archive
rebuilt once from the frozen `src_powerschool__*` externals (final ODBC pull
2026-07-01) by re-including the `powerschool` package with the ODBC staging
variant and 15 post-hooks in `dbt_project.yml`: `stg_powerschool__students` gets
the 8400 Focus prefix on `student_number`, and the 14 staging models with
`yearid` drop rows past AY2025 (`yearid > 35`). The package is removed again
after the prod build (#5012); the hook YAML in that PR is the rebuild recipe.
`int_fldoe__all_assessments` resolves `student_number` from
`int_focus__students`, not the archive. kipptaf reads the dataset as a BQ-native
source. Do not drop the dataset or the GCS files.

## Source Packages

Package list: `packages.yml` is ground truth (see `src/dbt/CLAUDE.md`). `focus`
— `focus_schema` points to `dagster_kippmiami_dlt_focus`. Miami does not use
`edplan`, `overgrad`, `pearson`, `powerschool`, or `titan` (`powerschool` is
temporarily included for the #5012 archive rebuild; see the PowerSchool
paragraph above).
