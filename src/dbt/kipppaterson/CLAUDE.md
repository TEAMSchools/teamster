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

PowerSchool data source: **SFTP** (`sftp.+enabled: true`,
`odbc.+enabled: false`)

This is the only NJ district using SFTP instead of ODBC for PowerSchool. Many
gradebook-related models (GPA, category grades, assignments) are explicitly
disabled.

## Active Source Packages

- `powerschool` (SFTP)
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
