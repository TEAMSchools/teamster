# CLAUDE.md — `dbt/kipppaterson/`

District-specific dbt project for **KIPP New Jersey - Paterson** schools. The
narrowest of the three NJ district projects — fewer enabled models than Newark
or Camden.

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
- `titan` — `stg_titan__person_data` only; `stg_titan__income_form_data`
  disabled (parity with Newark and Camden)
- `edplan` — `stg_edplan__njsmart_powerschool` and the regional
  `int_edplan__njsmart_powerschool_union` only.
  `stg_edplan__njsmart_powerschool_archive` is disabled (as in Newark and
  Camden) AND Paterson sets `edplan_has_archive: false`, which drops the archive
  leg from the regional union — the one-time NJSMART archive load predates
  Paterson's feed, so no `kipppaterson_edplan` archive table exists to read
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
