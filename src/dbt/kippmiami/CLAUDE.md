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
variant and 15 post-hooks: `stg_powerschool__students` got the 8400 Focus prefix
on `student_number`, and the 14 staging models with `yearid` dropped rows past
AY2025 (`yearid > 35`). The rebuild ran 2026-09-09 (#5012) and the package was
removed again; the `dbt_project.yml` hook YAML in #5201 is the rebuild recipe.
`int_fldoe__all_assessments` resolves `student_number` from
`int_focus__students`, not the archive. kipptaf reads the dataset as a BQ-native
source. Do not drop the dataset or the GCS files. A 16th hook belongs in that
recipe:
`stg_powerschool__calendar_day: +post-hook: delete from {{ this }} where date_value >= '2026-07-01'`.
The 2026-09-09 rebuild missed it and the rows were deleted by hand (#5197).

## Source Packages

Package list: `packages.yml` is ground truth (see `src/dbt/CLAUDE.md`). `focus`
— `focus_schema` points to `dagster_kippmiami_dlt_focus`. Miami does not use
`edplan`, `overgrad`, `pearson`, `powerschool`, or `titan`.
