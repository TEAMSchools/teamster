# Amplify: narrow the package move, alias the archive at kipptaf

Refs #5305. Supersedes the issue body's "per-district `int_` models" framing;
see _Why the scope narrowed_.

## Why the scope narrowed

The issue assumed each district's Amplify SFTP file carried that district's
rows. It does not. Amplify exports one account, and the file lands in Newark's
bucket. Measured on prod on 2026-09-14:

| Relation                                | Academic year | Regions present                      |
| --------------------------------------- | ------------- | ------------------------------------ |
| `kippnewark_amplify` benchmark          | 2025          | Newark 10 schools, Camden 4, Miami 2 |
| `kippnewark_amplify` benchmark          | 2026          | Newark 10, Camden 4, Paterson 2      |
| `kippnewark_amplify` aimline            | 2025          | NJ and Miami 16 schools, Paterson 2  |
| `kipppaterson_amplify` benchmark and PM | 2025 only     | Paterson 2                           |

Consequences:

- A kippnewark package model would hold Camden, Miami and Paterson rows. Region
  can only be resolved in kipptaf, through `int_people__location_crosswalk`.
- The base-plus-aimline PM combine cannot move to the package. Paterson's AY2025
  aimline rows sit in Newark's file while its PM rows sit in Paterson's, so the
  join only works after the kipptaf union.
- The benchmark unpivot cannot move either. The frozen API archive
  (`kipptaf_amplify.stg_amplify__benchmark_student_summary`, SY22-23 to SY24-25,
  NJ and Miami) needs the same unpivot, and it is a kipptaf-level table.
- Paterson's own file stopped at AY2025 while its rows now arrive through
  Newark's. The kipptaf union does not double-count today, but it will the day
  Paterson's feed resumes, and nothing would fail.

What does belong in the package: the `device_date` fallback and a PM surrogate
key that is unique. Both are value-only edits, so no contract changes and no
`zz_stg` seeding.

## Decisions

- Live SFTP column names win. The frozen archive is aliased to SFTP names once,
  at kipptaf, instead of renaming the live feed to the archive's names.
- Paterson double-count guard is a severity-error uniqueness test on the natural
  key at the kipptaf union. No dedupe logic, no source removal.
- `select * replace (...)` for same-name value swaps; `select * except (...)`
  plus an explicit `<old> as <new>` for renames. BigQuery rejects a rename in
  `replace` (`Column device_date in SELECT * REPLACE list does not exist`,
  verified by dry run).

## Package changes: `src/dbt/amplify/models/mclass/sftp/staging/`

`stg_amplify__mclass__sftp__pm_student_summary`

- `device_date` becomes `coalesce(device_date, sync_date) as device_date`, via
  `replace`. Today the kipptaf PM wrapper does this.
- Surrogate key widens to `student_primary_id_studentnumber`, `school_year`,
  `pm_period`, `measure`, `probe_number`, `device_date`, `assessment_grade`.
  Today it omits the last three and collides across a student's probes. Prod has
  zero collisions on the widened key across the whole union.
- `unique` on `surrogate_key`, severity error.

`stg_amplify__mclass__sftp__benchmark_student_summary`

- No SQL change. Add `unique` on `surrogate_key`, severity error. Prod is unique
  on it today.

`stg_amplify__mclass__sftp__pm_student_summary_aimline`

- Surrogate key widens the same way (`device_date`, `assessment_grade` added).
  Prod had 31 keys colliding on a student re-probed at a second grade; the
  widened key has zero collisions. Value-only.

All three get model-level `config.meta.contains_pii: true`. They are
student-level assessment content with names, ids and demographics.

## kipptaf changes: `src/dbt/kipptaf/models/amplify/mclass/`

### New API wrappers over the frozen archive

Two models under `api/staging/`, each `select * except (...) replace (...)` from
the `amplify` source in `sources-bigquery.yml`, tagged `contains_pii: true` at
model level because the tag does not travel through `source()`. This also gives
the archive the wrapper every kipptaf source is supposed to have.

`stg_amplify__mclass__api__benchmark_student_summary`

| Archive column                                        | Emits as                                            |
| ----------------------------------------------------- | --------------------------------------------------- |
| `reading_comprehension_maze_score`                    | `basic_comprehension_maze_score`                    |
| `reading_comprehension_maze_level`                    | `basic_comprehension_maze_level`                    |
| `reading_comprehension_maze_semester_growth`          | `basic_comprehension_maze_semester_growth`          |
| `reading_comprehension_maze_year_growth`              | `basic_comprehension_maze_year_growth`              |
| `reading_comprehension_maze_national_norm_percentile` | `basic_comprehension_maze_national_norm_percentile` |
| `reading_comprehension_maze_tested_out`               | `basic_comprehension_maze_tested_out`               |
| `reading_comprehension_maze_discontinued`             | `basic_comprehension_maze_discontinued`             |
| `dibels_composite_score_lexile`                       | `composite_score_lexile`                            |
| `official_teacher_staff_id`                           | `enrollment_teacher_staff_id`                       |
| `official_teacher_name`                               | `enrollment_teacher_name`                           |
| `client_date`                                         | `device_date`                                       |

`stg_amplify__mclass__api__pm_student_summary`

| Archive column                          | Emits as                                    |
| --------------------------------------- | ------------------------------------------- |
| `student_primary_id`                    | `student_primary_id_studentnumber`          |
| `official_teacher_staff_id`             | `enrollment_teacher_staff_id_teachernumber` |
| `official_teacher_name`                 | `enrollment_teacher_name`                   |
| `student_id_state_id`                   | `secondary_student_id_stateid`              |
| `client_date`                           | `device_date`                               |
| `coalesce(account_name, district_name)` | `district_name` (via `replace`)             |

Columns present on only one side stay null-filled on the other by
`union_relations`, as they are today.

### The three SFTP wrappers

`stg_amplify__mclass__sftp__pm_student_summary` drops its `device_date` fallback
and becomes a plain `select *` union like its two siblings. The `relationships`
tests on `school_name` stay.

### The two mClass intermediates

`int_amplify__mclass__benchmark_student_summary` and
`int_amplify__mclass__pm_student_summary` become: `union_relations` over the
SFTP wrapper and the API wrapper, the crosswalk join for `school`, `schoolid`,
`_dbt_source_project` and `region`, the Focus offset on the student id, and for
PM `matching_season` and the existing `coalesce(schoolid, school_primary_id)`.
Every other `coalesce` pair and the long `except` lists go away.

Their output columns take the SFTP names. Renamed outputs, prod name to new
name:

- Benchmark: `reading_comprehension_maze_*` to `basic_comprehension_maze_*` (7
  columns; `reading_comprehension_maze_local_percentile` becomes
  `basic_comprehension_maze_local_percentile`), `dibels_composite_score_lexile`
  to `composite_score_lexile`, `official_teacher_*` to `enrollment_teacher_*`,
  `client_date` to `device_date`.
- PM: `client_date` to `device_date`, `official_teacher_staff_id` to
  `enrollment_teacher_staff_id_teachernumber`, `official_teacher_name` to
  `enrollment_teacher_name`, `student_id_state_id` to
  `secondary_student_id_stateid`. `student_primary_id` keeps its name: it is the
  Focus-offset network number, derived here.

Each gets a `dbt_utils.unique_combination_of_columns` test at severity error:

- Benchmark: `student_primary_id`, `school_year`, `benchmark_period`,
  `assessment_grade`.
- PM: those four plus `measure`, `probe_number`, `device_date`.

These are the Paterson guard.

### Consumer edits, all inside `models/amplify/`

| Model                                                    | Edit                                                                                                                               |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `int_amplify__mclass__benchmark_student_summary_unpivot` | 5 `reading_comprehension_maze_*` refs become `basic_comprehension_maze_*`; the `'Reading Comprehension (Maze)'` label is unchanged |
| `int_amplify__benchmark_student_summary`                 | `bss.client_date` becomes `bss.device_date as client_date`                                                                         |
| `int_amplify__all_assessments`                           | `p.client_date` becomes `p.device_date`, aliased `client_date`, in the select and the window join of the Internal branch           |
| `int_amplify__mclass__pm_student_summary_aimline`        | none; it reads the SFTP wrappers directly and already uses SFTP names                                                              |

No model outside `models/amplify/` changes.
`int_amplify__benchmark_student_summary`, `int_amplify__all_assessments` and the
`pm_met_criteria` pair keep their output columns, so the 17 kipptaf consumers
and every exposure are untouched.

### Not moved, and why

- Unpivot: the archive needs it too.
- Base-plus-aimline combine: needs the kipptaf union first (Paterson).
- Crosswalk join, Focus offset, expectation gates, participation roster: join
  non-Amplify sources.
- `int_amplify__dds__data_farming_unpivot`: disabled in kipptaf, frozen SY24
  data. Out of scope.

## Rollout

One PR. Package edits are value-only, so no `zz_stg` seeding and no two-PR
pattern. The modified PM SFTP wrapper is `state:modified`, and CI rebuilds it
from the district `zz_stg` copies, which have the same column set.

Local build order:

1. `uv run dbt build --select stg_amplify__mclass__sftp__pm_student_summary`
   with `--project-dir` on kippnewark, then kipppaterson, target dev.
2. `uv run dbt build --select stg_amplify__mclass__sftp__pm_student_summary+` on
   kipptaf, target dev with `--defer --favor-state`, so the chain through
   `int_amplify__all_assessments` and its tests runs on the new shape.

Prod ordering has no hazard: the package change deploys to the district code
locations, and kipptaf reads their prod tables with an unchanged column set.

## Verification against prod

Before opening the PR, on the dev or CI schema against prod:

1. Row count and distinct natural key on
   `int_amplify__mclass__benchmark_student_summary`,
   `int_amplify__mclass__pm_student_summary`, `int_amplify__all_assessments` and
   `rpt_tableau__dibels_dashboard`. All four must match.
2. Column-by-column value diff on the two mClass intermediates, joined on the
   natural key, with renamed columns paired (prod
   `reading_comprehension_maze_score` against branch
   `basic_comprehension_maze_score`, and so on). Zero differing values.
3. The one expected change: the PM `surrogate_key` hash differs on every PM row,
   in the intermediate and wherever it is passed through
   (`int_amplify__all_assessments.surrogate_key` on PM rows). Confirm nothing
   joins on it. The DIBELS skill already records that it must not be used as a
   probe-level key.

## Docs

- Rewrite `src/dbt/amplify/CLAUDE.md`: one Amplify account, network-wide, lands
  in Newark's bucket; the package staging is the live feed; kipptaf wraps it and
  unions the frozen archive aliased to SFTP names. Remove the line that says
  kipptaf keeps its own native amplify models.
- `.claude/skills/dibels-dashboard/SKILL.md`: the paragraph saying the PM
  surrogate key still collides across probes becomes past tense, with the
  widened key named.
- Update the #5305 issue body to this scope before opening the PR, keeping its
  "For Claude" fold-out.

## Open items

- PII scope on the five tagged models is tiers 1 to 3 (direct identifiers plus
  student-level content). Confirm or narrow.
- The Paterson SFTP feed: someone should ask Amplify whether Paterson
  Preparatory is now inside the network account for good. If so, the Paterson
  package models and the `kipppaterson_amplify` sources can be disabled in a
  follow-up, and the guard tests stay.
