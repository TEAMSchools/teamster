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
built from the frozen `src_powerschool__*` externals (final ODBC pull
2026-07-01). It was rebuilt on 2026-09-09 (#5012). It was rebuilt again after
#5231 merged, adding identity and school columns to the GPA, final grades,
calendar day, and student enrollment models, and a third time after #5250 to
carry calendar-week fields on `int_powerschool__ps_adaadm_daily_ctod` (#5193).
The recipe is the `dbt_project.yml` `powerschool:` block: re-include the package
with the ODBC staging variant and 16 post-hooks — the 8400 Focus prefix on
`student_number` (`stg_powerschool__students`), 14 staging models with `yearid`
dropping rows past AY2025 (`yearid > 35`), and `stg_powerschool__calendar_day`
deleting `date_value >= '2026-07-01'`. The package is re-included for each
rebuild and removed after. `int_fldoe__all_assessments` resolves
`student_number` from `int_focus__students`, not the archive. kipptaf reads the
dataset as a BQ-native source. Do not drop the dataset or the GCS files.

## Source Packages

Package list: `packages.yml` is ground truth (see `src/dbt/CLAUDE.md`). `focus`
— `focus_schema` points to `dagster_kippmiami_dlt_focus`. Miami does not use
`edplan`, `overgrad`, `pearson`, `powerschool`, or `titan`.
