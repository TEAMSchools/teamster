# CLAUDE.md — `dbt/amplify/`

Source-system staging project for **Amplify** reading assessments. Covers two
product lines with different ingestion paths, split into method subfolders:

- `dds/` — Amplify DDS (SFTP file drops)
- `mclass/api/` — mClass API data
- `mclass/sftp/` — mClass SFTP file drops

`dds` and `mclass/api` can be independently enabled/disabled per school in the
consuming project's `dbt_project.yml` (e.g. `kipppaterson` disables both).

## One network account, landing in Newark's bucket

Amplify exports one account for the whole network, and the mClass SFTP files
land in `kippnewark`'s bucket. The `kippnewark` copies of the `mclass/sftp`
staging models therefore carry Camden, Miami and Paterson schools too, and
`_dbt_source_relation` on a kipptaf union over them is NOT region. Region is
resolved in kipptaf from `int_people__location_crosswalk` on `school_name`.
Paterson Preparatory is inside the network account now; `kipppaterson`'s own
file holds AY2025 only and is kept as the archive of those rows, so its package
models stay enabled and kipptaf carries natural-key uniqueness tests on its
mClass intermediates so a Paterson row arriving through both files fails instead
of doubling.

## What lives here versus kipptaf

Here: casts, measure-name normalization, the `device_date` fallback to
`sync_date`, and a surrogate key that is unique per row. Nothing that needs
another source.

kipptaf (`models/amplify/`): `select *` union wrappers over the two districts,
two `stg_amplify__mclass__api__*` wrappers that alias the frozen SY22-25 API
archive to this package's SFTP column names, the crosswalk join, the Miami Focus
student-number offset, the benchmark unpivot, and the base-plus-aimline PM
combine. The last two stay in kipptaf because the archive needs the unpivot too
and the aimline combine only works after the union.

A column ADD or rename on a contracted staging model here needs the two-PR
pattern or `zz_stg_` seeding for Newark and Paterson
(`.claude/rules/dbt-models.md`). A value-only change does not. A value that
MOVES between the package and kipptaf still needs the old site to keep computing
it until every district has rebuilt; the kipptaf PM wrapper's `device_date`
fallback is that case.
