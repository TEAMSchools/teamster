# CLAUDE.md — `dbt/kipppaterson/`

District-specific dbt project for **KIPP New Jersey - Paterson** schools. The
most limited district project — PowerSchool only, with a narrower set of enabled
models compared to Newark and Camden.

## Model Structure

```text
models/
  powerschool/   # district-specific PowerSchool staging (refs powerschool package)
    sis/staging/
  pearson/       # district-specific Pearson intermediates (refs pearson package staging)
    intermediate/
```

PowerSchool data source: **dlt** (the package default; `odbc` and `sftp` are
off). Paterson disables a set of grad-plan and gradebook `stg_powerschool__*`
dlt models its PowerSchool instance does not populate — see the
`powerschool.sis.staging.dlt` block in `dbt_project.yml`.

## Source Packages

Package list: `packages.yml` is ground truth (see `src/dbt/CLAUDE.md`).
Endpoint-level notes:

- `pearson` — `stg_pearson__njsla` and `stg_pearson__njsla_science` enabled;
  `stg_pearson__njgpa`, `stg_pearson__parcc`, `stg_pearson__student_test_update`
  disabled in `dbt_project.yml`
- `amplify` — both `dds` and `mclass/api` disabled
- `finalsite`
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
