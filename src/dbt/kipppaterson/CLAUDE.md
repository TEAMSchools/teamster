# CLAUDE.md — `dbt/kipppaterson/`

District-specific dbt project for **KIPP New Jersey - Paterson** schools.

## Model Structure

```text
models/
  powerschool/   # district-specific PowerSchool staging (refs powerschool package)
    sis/staging/
  pearson/       # district-specific Pearson intermediates (refs pearson package staging)
    intermediate/
```

Paterson disables a set of grad-plan and gradebook `stg_powerschool__*` dlt
models its PowerSchool instance does not populate — see the
`powerschool.sis.staging.dlt` block in `dbt_project.yml`.

## Source Packages

Endpoint-level notes:

- `cambium` — `stg_cambium__njsla` only. `stg_cambium__njgpa` and its source are
  disabled in `dbt_project.yml`, and so are its generic tests, listed
  individually under `data_tests:` — a disabled model keeps its tests, and they
  would scan a relation Paterson never builds. Quoted columns (`period`) get a
  trailing underscore in the test name. A first Paterson end-of-course file
  loads through `stg_cambium__njsla` with no change here
- `pearson` — `stg_pearson__student_list_report` and
  `int_pearson__student_list_report` only. The score models
  (`stg_pearson__njsla*`, the local `int_pearson__njsla*` remaps and
  `int_pearson__all_assessments`) are disabled with their tests, leaving the
  last prod tables frozen as history for kipptaf. `stg_pearson__njgpa`,
  `stg_pearson__parcc` and `stg_pearson__student_test_update` were never enabled
  here
- `deanslist` — `behavior`, `comm_log`, `incidents`, `roster_assignments`,
  `rosters`, `students`, `terms`, and `users` endpoints pulled. The
  `stg_deanslist__dff_stats`, `stg_deanslist__followups`,
  `stg_deanslist__homework`, and `stg_deanslist__lists` staging models (and
  their `src_deanslist__*` sources) are disabled in `dbt_project.yml` — Paterson
  does not pull those endpoints, so no Avro exists for them

## Models in package-named directories

`models.<package>:` in `dbt_project.yml` configures the imported package.
kipppaterson's own models in `models/<package>/` go under
`models.kipppaterson.<package>:` and need `+schema: <package>` to land in
`kipppaterson_<package>` schema.
