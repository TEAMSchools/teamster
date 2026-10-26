# Pearson archive and Cambium split

Issue: [#5591](https://github.com/TEAMSchools/teamster/issues/5591)

## Goal

Split `int_pearson__all_assessments` by vendor. Pearson ran New Jersey state
testing through December 2025 and its data will never change, so it freezes.
Cambium runs every administration from Spring 2026 on, so its mapping becomes a
live model in the `cambium` package, built once per district. A new kipptaf
model, `int_assessments__state_nj_scores`, unions the two and is the one place
kipptaf reads New Jersey state scores from. Columns take neutral names at the
same time.

Success looks like this:

- Pearson history stops rebuilding in the 3 district projects.
- The Cambium-to-state-score mapping lives in one place, the `cambium` package.
- `int_assessments__state_nj_scores` matches today's
  `int_pearson__all_assessments` row for row, under the new column names.
- No kipptaf model, test or analysis reads `int_pearson__all_assessments`.

Out of scope, each a follow-up issue:

- Retiring the rest of the `pearson` package. `int_pearson__student_list_report`
  (the prelim feed) still reads it in all 3 districts, and the prelim gates in
  the state assessments dashboard and demographic comps depend on it.
- Retiring kipptaf's `stg_cambium__*` union wrappers, which nothing reads after
  this change.

## Current state

Verified on `origin/main` at `7279c1eb4f`, prod counts on 2026-09-28.

- `kipptaf_pearson.int_pearson__all_assessments` is a **view**. It unions the 3
  district `int_pearson__all_assessments` relations with 6 CTEs that map
  kipptaf's `stg_cambium__njsla`, `stg_cambium__eoc` and `stg_cambium__njgpa`
  into Pearson's column shape. The outer select casts `statestudentidentifier`
  to string, coalesces `localstudentidentifier` from
  `stg_google_sheets__pearson__student_crosswalk`, and adds
  `_dbt_source_project`.
- The district
  `kipp{newark,camden,paterson}_pearson.int_pearson__all_assessments` relations
  are **tables**, built by the `pearson` package. They are pre-crosswalk.
- Paterson disables `stg_cambium__njgpa` and `stg_cambium__eoc`, and reads its
  own `int_pearson__njsla*` remaps through the
  `pearson_state_assessment_relations` var.

| Source table                 | Assessment              | Years     |  Rows |
| ---------------------------- | ----------------------- | --------- | ----: |
| `stg_pearson__parcc`         | PARCC                   | 2015-2017 | 15625 |
| `stg_pearson__njsla`         | NJSLA                   | 2018-2024 | 44209 |
| `stg_pearson__njsla_science` | NJSLA Science           | 2021-2024 |  6804 |
| `stg_pearson__njgpa`         | NJGPA                   | 2021-2025 |  4130 |
| `int_pearson__njsla`         | NJSLA                   | 2023-2024 |   324 |
| `int_pearson__njsla_science` | NJSLA Science           | 2023-2024 |   116 |
| `stg_cambium__njsla`         | NJSLA and NJSLA Science | 2025      | 11893 |
| `stg_cambium__njgpa`         | NJGPA                   | 2025      |   813 |
| `stg_cambium__eoc`           | NJSLA                   | 2025      |   504 |

Pearson total 71208, Cambium total 13210.

## Design

### Shape

```text
kipp*_pearson.int_pearson__all_assessments (frozen tables) ─┐
                                                           ├─► int_assessments__state_nj_scores ─┐
kipp*_cambium.int_cambium__all_assessments (live) ─────────┘                                     ├─► int_assessments__state_scores
                                                               int_fldoe__all_assessments ───────┘
```

The archive follows the kipptaf archive pattern, applied at region level. The
district tables already hold the frozen rows, so no warehouse DDL is needed:
disabling the district models leaves their tables in place, and kipptaf keeps
reading them through the
`source("kipp*_pearson", "int_pearson__all_assessments")` entries it already
declares. The kipptaf view cannot serve as the archive: a disabled view still
recomputes over its upstreams on every read and carries the Cambium rows.

### Column names

Two rules, in priority order:

1. A column `int_assessments__state_scores` already exposes takes its name
   there.
2. Any other column takes the name `stg_cambium__*` uses. Pearson-only columns
   that are already snake_case keep their names.

25 columns rename. The other 31 keep their names.

| Current                                | New                                         | Rule |
| -------------------------------------- | ------------------------------------------- | ---- |
| `localstudentidentifier`               | `student_number`                            | 1    |
| `statestudentidentifier`               | `state_student_id`                          | 1    |
| `admin`                                | `administration_round`                      | 1    |
| `gradelevelwhenassessed`               | `grade_level_when_assessed`                 | 1    |
| `testscalescore`                       | `scale_score`                               | 1    |
| `testperformancelevel`                 | `performance_level`                         | 1    |
| `testperformancelevel_text`            | `performance_level_label`                   | 1    |
| `subject`                              | `raw_subject`                               | 1    |
| `njsla_aggregated_proficiency`         | `aggregated_proficiency`                    | 1    |
| `njsla_performance_band_group_label`   | `performance_band_group_label`              | 1    |
| `studenttestuuid`                      | `student_test_uuid`                         | 2    |
| `assessmentyear`                       | `assessment_year`                           | 2    |
| `assessmentgrade`                      | `assessment_grade`                          | 2    |
| `testcode`                             | `test_code`                                 | 2    |
| `testscorecomplete`                    | `test_score_complete`                       | 2    |
| `firstname`                            | `first_name`                                | 2    |
| `lastorsurname`                        | `last_or_surname`                           | 2    |
| `studentwithdisabilities`              | `student_with_disabilities`                 | 2    |
| `englishlearnerel`                     | `multilingual_learner`                      | 2    |
| `hispanicorlatinoethnicity`            | `hispanic_or_latino_ethnicity`              | 2    |
| `americanindianoralaskanative`         | `american_indian_or_alaska_native`          | 2    |
| `blackorafricanamerican`               | `black_or_african_american`                 | 2    |
| `nativehawaiianorotherpacificislander` | `native_hawaiian_or_other_pacific_islander` | 2    |
| `twoormoreraces`                       | `two_or_more_races`                         | 2    |

None of the renamed columns feed a surrogate key. `dim_assessments`,
`dim_assessment_administrations` and `fct_assessment_scores_enrollment_scoped`
hash `assessment_type`, `module_code`, `academic_year` and
`administration_period`, which keep their names.

### PR 1: `cambium` package and district projects

- New `src/dbt/cambium/models/intermediate/int_cambium__all_assessments.sql`,
  built from the 6 kipptaf Cambium CTEs. It reads the package's own
  `stg_cambium__*` models and outputs the new column names. It does not apply
  the student crosswalk or derive `_dbt_source_project`; kipptaf does both.
- A `cambium_state_assessment_relations` package var lists the staging models it
  reads, following `pearson_state_assessment_relations`. The NJSLA and EOC union
  reads the listed relations, and the NJGPA branch compiles only when
  `stg_cambium__njgpa` is listed. Paterson overrides the var to
  `stg_cambium__njsla`.
- Properties YAML with a uniqueness test on `student_test_uuid`.
- In each district `dbt_project.yml`, disable `int_pearson__all_assessments`,
  the `stg_pearson__*` models that feed only it, Paterson's `int_pearson__njsla`
  and `int_pearson__njsla_science`, and the tests on each.
  `int_pearson__student_list_report` and the sources it reads stay enabled.
  kipptaf's own `stg_pearson__*` wrappers, which the tiered-crosswalk analysis
  reads, keep reading the frozen district tables unchanged.

Between the PRs, Dagster materializes `int_cambium__all_assessments` in all 3
districts. kipptaf CI reads district sources from the `zz_stg_*` copies, so
before PR 2's CI each district needs
`dbt clone --select int_cambium__all_assessments --target staging --state src/dbt/<district>/target/prod --full-refresh --project-dir src/dbt/<district>`.
The clone recreates shared staging tables, so the user runs or approves it.

### PR 2: kipptaf

- New
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__state_nj_scores.sql`,
  materialized as a table. A Pearson CTE unions the 3 frozen district tables
  with an explicit column list, renamed per the map. A Cambium CTE unions the 3
  district `int_cambium__all_assessments` tables. A positional `union all` joins
  them. The outer select casts `state_student_id` to string, coalesces
  `student_number` from the student crosswalk on `student_test_uuid`, and
  derives `_dbt_source_project`.
- Grain tests move from `int_pearson__all_assessments`:
  `unique_combination_of_columns(student_test_uuid)`, and
  `unique_combination_of_columns(student_number, academic_year, aligned_test_code, administration_round)`
  where `student_number is not null`, `severity: error`. The second must run
  over the union: AY2025 NJGPA exists in both vendors.
- New `sources-kipp*.yml` entries in `src/dbt/kipptaf/models/cambium/` for the
  district `int_cambium__all_assessments` tables.
- Disable `int_pearson__all_assessments` and its tests.
- Repoint the 10 readers to `int_assessments__state_nj_scores` and apply the
  renames:

| Reader                                                                                   | Renamed columns it reads                                                                                                           |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `int_assessments__state_scores` (New Jersey branch)                                      | all 10 rule-1 columns; the branch becomes a plain column list, with `season` from `administration_round`                           |
| `rpt_deanslist__state_test_scores`                                                       | `localstudentidentifier`, `assessmentyear`, `subject`, `testscalescore`, `testperformancelevel_text`                               |
| `dim_assessments`                                                                        | `testscalescore` (in `where` only)                                                                                                 |
| `dim_assessment_administrations`                                                         | `testscalescore` (in `where` only)                                                                                                 |
| `int_students__graduation_pathway_scores`                                                | `testscalescore`, `testcode`, `testscorecomplete`, `localstudentidentifier`; both unit-test fixtures in its YAML are rewritten too |
| `int_tableau__state_assessments_demographic_comps` (prelim gate)                         | `admin`                                                                                                                            |
| `rpt_tableau__state_assessments_dashboard` (prelim gate)                                 | `admin`                                                                                                                            |
| `tests/test_incorrect_student_number_pearson.sql`                                        | `studenttestuuid`, `localstudentidentifier`, `statestudentidentifier`, `firstname`, `lastorsurname`, `testcode`                    |
| `tests/stg_google_sheets__assessments__vendor_subject_crosswalk__covers_all_sources.sql` | `subject`                                                                                                                          |
| `analyses/state_assessment_tiered_crosswalk_match.sql`                                   | `studenttestuuid`, `localstudentidentifier`, `statestudentidentifier`, `firstname`, `lastorsurname`                                |

The prelim gates must read `int_assessments__state_nj_scores`, not the frozen
tables: every future official year is Cambium, and the gate turns the prelim
branch off when official scores land.

YAML that names the old model also changes: the 4
`meta.source_column: int_pearson__all_assessments.*` strings in
`int_assessments__score_anchors.yml` and
`int_assessments__resolved_section_enrollments.yml`, the `meta.dagster.ref.name`
on `test_incorrect_student_number_pearson` in `tests/properties.yml`, and
description text in 7 property files. Cube and `docs/` have no references.

## Verification

Every comparison runs against prod and reports counts only.

PR 1:

- `uv run dbt build --select int_cambium__all_assessments` with `--defer` in
  each district. Paterson compiles with only `stg_cambium__njsla`.
- Per district, the dev output with the crosswalk applied, `EXCEPT DISTINCT` in
  both directions against the Cambium rows of prod
  `kipptaf_pearson.int_pearson__all_assessments`, old columns selected under the
  new names: 0 both ways. Per source table counts hold at 11893, 813 and 504.
- `dbt parse --no-partial-parse` on `main` and on the branch in each district;
  the diff of enabled nodes lists only the intended Pearson models and tests,
  and `int_pearson__student_list_report` survives.

PR 2:

- `int_assessments__state_nj_scores` against prod
  `int_pearson__all_assessments`, `EXCEPT DISTINCT` in both directions over all
  56 columns with old names mapped to new: 0 both ways, 71208 Pearson plus 13210
  Cambium rows. Both grain tests pass.
- Full-row `EXCEPT DISTINCT` in both directions against prod, 0 both ways:
  `int_assessments__state_scores`, `rpt_deanslist__state_test_scores`,
  `int_students__graduation_pathway_scores`, `dim_assessments`,
  `dim_assessment_administrations`,
  `int_tableau__state_assessments_demographic_comps` and
  `rpt_tableau__state_assessments_dashboard`. Key set of
  `fct_assessment_scores_enrollment_scoped` both ways.
- The 2 rewritten unit tests in `int_students__graduation_pathway_scores` pass.
- `test_incorrect_student_number_pearson` and the crosswalk-coverage test return
  the same failing-row counts as on prod.
- `rg 'int_pearson__all_assessments' src/dbt/kipptaf --glob '*.{sql,yml,md}'`
  finds only the disabled model's own files and the district source
  declarations.

## Accepted trade-offs

- Pearson's `aligned_*` bands and labels freeze at today's definitions. If the
  network redefines a band, the Pearson years will not follow.
- `englishlearnerel` becomes `multilingual_learner`, Cambium's term for the same
  flag.
- PR 2 changes every New Jersey reader in one step. A rename and a vendor split
  in one change make the row-for-row proof depend on the column map, which is
  why the map is written out above.
