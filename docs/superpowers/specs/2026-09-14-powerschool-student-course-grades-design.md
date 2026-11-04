# Move the PowerSchool course-grade joins behind `rpt_tableau__student_course_grades` into the package

Refs #5285. Refs #5260. Refs #5012.

Covers row 1 of #5285: `rpt_tableau__student_course_grades`, the last kipptaf
extract that rebuilds PowerSchool-to-PowerSchool joins at course grain. Row 2
shipped in #5306.

Follows the pattern set by
`docs/superpowers/specs/2026-09-11-powerschool-section-teachers-design.md` and
`docs/superpowers/specs/2026-09-11-powerschool-gradebook-assignment-scores-design.md`:
one package model carrying every PowerSchool-internal join, a kipptaf
`union_relations` wrapper above it, and the kipptaf-only joins left in kipptaf.

## Decision

Build one new package model, `int_powerschool__student_course_grades_spine`, at
the consumer's own grain: one row per student, term, course, and gradebook
category, for the current and prior academic year. It absorbs every course-grain
CTE the consumer holds today, including the temporary #4687 prior-year
reconstruction. kipptaf reads it through a bare `union_relations` wrapper, and
`rpt_tableau__student_course_grades` becomes the student roster joined once to
that wrapper plus its 2 kipptaf enrichment joins. One PR. No Miami, no archive
rebuild.

The bar, set on 2026-09-14: every PowerSchool-to-PowerSchool join leaves
kipptaf. Not "the consumer reads a wrapper somewhere", and not "row-identical is
enough".

## Why the issue's easy paths do not work

#5260's table said `base_powerschool__final_grades` "already carries enrollment
attributes", so the move was a swap. Re-measured against prod on 2026-09-14 in
all 3 NJ districts:

- `base_powerschool__final_grades` has no `sections_dcid`,
  `sections_section_number`, `sections_external_expression`, or
  `rn_course_number_year`. All 4 exist on
  `base_powerschool__course_enrollments`.
- It filters to `cc_academic_year = current_academic_year` at line 56. The
  consumer reads the prior year at lines 104, 306, and 362.

Widening `base_powerschool__final_grades` to 2 years would change cost and
semantics for every other consumer, and it is term-grain, so it still could not
carry the category rows.

### What the dashboard actually reads

The Academic & Gradebook Health Suite workbook (LUID
`b3c14d67-3130-46ac-82a0-0637a5cc2da5`, pulled 2026-09-14 08:17 UTC, 94
worksheets) was parsed for per-worksheet `datasource-dependencies` on the
`rpt_tableau__student_course_grades` datasource. Tableau lists every view column
in datasource metadata, so a bare name match proves nothing; the counts below
are worksheets that depend on the column or a calculation over it.

| Column                           | Worksheets | Note                                                  |
| -------------------------------- | ---------: | ----------------------------------------------------- |
| `sections_dcid`                  |          0 | dead in Tableau                                       |
| `section_number`                 |          0 | feeds `section_or_period`                             |
| `external_expression`            |          0 | feeds `section_or_period`                             |
| `section_or_period`              |          6 | includes the DeansList export and office-hours roster |
| `credit_type`                    |         16 |                                                       |
| `course_name`                    |          6 |                                                       |
| `teacher_name`                   |          7 |                                                       |
| `manager`                        |         10 |                                                       |
| `is_current_academic_year`       |         13 | gates the landing-page tile calculations              |
| `academic_year`                  |         26 |                                                       |
| `teacher_tableau_username`       |          0 | 10 references outside worksheets: row-level security  |
| `school_leader_tableau_username` |          0 | 15 references outside worksheets: row-level security  |

Zero worksheets read `date_enrolled`, `exclude_from_gpa`, `teacher_number`,
`report_to_sam_account_name`, `tutoring_nj`, `nj_student_tier`, or
`academic_year_display`. They stay in the contract; dropping them is a separate
decision.

So 3 of the 4 missing columns are load-bearing through `section_or_period`, and
the prior year is load-bearing through 13 worksheets. `rn_course_number_year` is
a model-internal pick.

## The package model

`src/dbt/powerschool/models/sis/intermediate/int_powerschool__student_course_grades_spine.sql`

Grain: one row per `studentid`, `yearid`, `quarter`, `course_number`,
`category_name_code`, where `quarter` is Q1 to Q4 or Y1 and Y1 rows carry a null
category. Years: `current_academic_year - 1` and `current_academic_year`, from
the district var, the same way `base_powerschool__final_grades` filters at
line 56.

Inputs, all package refs, all already in the package:

| Ref                                      | Role                                      |
| ---------------------------------------- | ----------------------------------------- |
| `base_powerschool__course_enrollments`   | drives the model; one row per enrollment  |
| `base_powerschool__final_grades`         | current-year live term and Y1 grades      |
| `stg_powerschool__storedgrades`          | stored Y1, prior-year term grades, #4687  |
| `int_powerschool__category_grades`       | category term and running percents        |
| `int_powerschool__gradescaleitem_lookup` | #4687 banding and the whole-letter ladder |

The SQL is the consumer's course-grain CTEs moved verbatim. Moved:
`course_enrollments` (minus its 2 kipptaf left joins), `y1_final_grades`,
`backfill_quarter_running`, `backfill_y1_stored_raw`, `backfill_y1_stored`,
`backfill_course_anchored`, `backfill_running_course`, `quarter_grades`,
`grade_scale_rungs`, `grade_scale_ladder`, `category_grades`, `category_ranked`,
`category_drivers`, `course_priority`. The final select drives from
`course_enrollments` and left-joins the rest on the same keys the consumer uses
today, so an enrollment with no grade row survives with null grade columns.

Deletions, and nothing else:

| Deletion                                                         | Reason                                       |
| ---------------------------------------------------------------- | -------------------------------------------- |
| every `_dbt_source_project` column, partition key, and predicate | one project is one region inside the package |
| every `_dbt_source_relation` pass-through                        | the wrapper re-adds it                       |

Everything else survives as written: the lunch, study-hall, and advisory course
exclusion list, the `rn_course_number_year = 1` and `cc_sectionid > 0` picks,
the `not is_dropped_section` guards, the `termbin_start_date <= current_date`
gates, the `(x is null) asc` orderings in `category_ranked`, the 3
`quarter_grades` branches, and every `TODO(#4687)` comment. The #4687 code is
scheduled to die; after this move it dies in one place, the package.

### Output columns

Every column the consumer takes today from `ce`, `y1f`, `qg`, `c`, `cd`, `gsl`,
and `cp`, under the same names, plus:

- `studentid`, `yearid`, `quarter`: the join keys to the kipptaf roster.
- `courses_gradescaleid`: carried for the ladder join, which now happens inside
  the model.
- `teachernumber` and `teacher_lastfirst`, so kipptaf can join
  `int_people__staff_roster`.
- `need_next`: a pure function of `need_60`, `need_70`, and
  `need_next_cutoff_percent`, all package columns, so it moves.

`students_student_number` is not projected. The consumer takes `student_number`
from the roster, and the model carries no PII beyond what
`base_powerschool__final_grades` already holds at this layer: student-level
grades keyed by surrogate `studentid`, tagged `contains_pii` in its properties
yml.

### `section_or_period` stays in kipptaf

The consumer computes
`if(s.grade_level < 9, ce.section_number, ce.external_expression)` from the
roster's grade level for the year. The only grade level on the enrollment row is
`students_grade_level`, which `base_powerschool__course_enrollments` takes from
`stg_powerschool__students.grade_level`, the student's CURRENT grade. Measured
against prod on 2026-09-14 for the 2-year window, `rn_course_number_year = 1`,
`cc_sectionid > 0`:

| Region   | Year |   Rows | Grade differs | Crosses the grade 9 line |
| -------- | ---- | -----: | ------------: | -----------------------: |
| Newark   | 2025 | 41,111 |        35,354 |                    2,144 |
| Newark   | 2026 | 42,153 |             0 |                        0 |
| Camden   | 2025 | 13,311 |        10,980 |                      613 |
| Camden   | 2026 | 14,033 |             0 |                        0 |
| Paterson | 2025 |  3,924 |         3,665 |                        0 |
| Paterson | 2026 |  3,826 |             0 |                        0 |

The prior year differs on every promoted student, and 2,757 rows would flip
between section number and period. So the package model exports `section_number`
and `external_expression`, and `section_or_period` stays where it is in the
consumer's select list, reading the roster's `grade_level`.

### Uniqueness test

`dbt_utils.unique_combination_of_columns` on the 5 grain columns, at
`severity: warn` with the same `TODO(#3915)` comment the consumer carries: the
prior-year storedgrades double-write duplicates move with the data. Restoring
`severity: error` belongs to #3915.

## The kipptaf wrapper

`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__student_course_grades_spine.sql`

A bare `union_relations` over `kippnewark_powerschool`,
`kippcamden_powerschool`, and `kipppaterson_powerschool` plus
`extract_source_project()`, the same shape as
`int_powerschool__gradebook_assignments` in that directory. Miami is absent and
stays absent: the dashboard hard-excludes it at line 366 of the consumer, and
`kippmiami` does not consume the package.

The wrapper's properties yml re-declares `config.meta.contains_pii: true` at
model level, since the tag does not travel through `source()`, and carries the
6-column uniqueness test (the 5 grain columns plus `_dbt_source_project`) at
`severity: warn`, `TODO(#3915)`.

One source entry is added to each of `sources-kippnewark.yml`,
`sources-kippcamden.yml`, and `sources-kipppaterson.yml`, with the
`staging`-to-`zz_stg_` schema branch the neighbors already carry.

## The consumer rewrite

`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`

Keeps: `term`, `prior_year_gpa_rollup`, `prior_year_gpa`,
`prior_year_cumulative`, `backfill_running_gpa`, `student_roster`. All are
student-grain or roster-driven, and read kipptaf cross-SIS models
(`int_students__terms`, `int_extracts__student_enrollments`) or the
student-grain GPA wrappers. The GPA joins hang off the kipptaf roster, so they
are not PowerSchool-to-PowerSchool and are out of scope.

Deletes: every CTE from `course_enrollments` down through `course_priority`.

The final select becomes `student_roster` left-joined once to the wrapper on
`studentid`, `yearid`, `quarter`, and `_dbt_source_project`, then the 2
enrichment joins that used to sit inside `course_enrollments`:

```sql
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as f
    on g.studentid = f.studentid
    and g.academic_year = f.academic_year
    and g.credit_type = f.powerschool_credittype
    and g._dbt_source_project = f._dbt_source_project
    and f.rn_year = 1
left join
    {{ ref("int_people__staff_roster") }} as r
    on g.teachernumber = r.powerschool_teacher_number
```

The select list, column order, and contract do not change. `section_or_period`,
the 2 GPA-band deltas, `is_gpa_band_slide`, and
`y1_course_letter_grade_adjusted` stay as written in the select list, reading
roster columns and wrapper columns by the same names as today. The
`where s.quarter_start_date <= current_date` filter stays.

Today the enrichment joins run on the enrollment row before any grade join, so a
course with no grade row still gets `tutoring_nj` and `manager`. In the rewrite
they run on the wrapper row, which carries every enrollment because the package
model drives from `course_enrollments`. Same result; proved in verification, not
asserted.

## Verification

Against production relations only. No dev build, and no `zz_stg` copy: kipptaf
`source()` resolves to personal `zz_<user>_*` copies under `target=dev`, and a
`zz_stg` comparison measures staging staleness, not the change (the false alarm
on #5281).

1. Compile the package model at `--target prod` per NJ district. Run the
   compiled SQL as a CTE against that district's prod
   `kipp<district>_powerschool` relations. Record the row count and slot time
   per district; Newark is the largest input and the cost goes in the PR body.
2. Run the rewritten consumer the same way, with the wrapper replaced by a
   `union all` of the 3 district CTEs plus a literal `_dbt_source_project`.
3. Compare to prod `kipptaf_tableau.rpt_tableau__student_course_grades` with
   `except distinct` in both directions, chunked by `academic_year` and
   `_dbt_source_project`, over every contract column. Fingerprint each chunk
   with `sum(cast(farm_fingerprint(...) as bignumeric))`; a plain `sum`
   overflows.
4. Expected: 0 differences, except rows whose only cause is the #3915
   storedgrades tie-break, proved the way #5306 proved it: every differing row
   sits on a
   `(student_number, academic_year, schoolname, course_number, course_name)` key
   with 2 or more stored rows carrying different values.
5. Named checks: `section_or_period` is byte-identical (it did not move);
   `tutoring_nj`, `nj_student_tier`, `manager`, and `teacher_tableau_username`
   are identical on rows with null `quarter_course_percent_grade` (the
   enrichment-ordering claim).
6. The package model's uniqueness test runs in all 3 districts and reports the
   same duplicate count as the consumer's test does today for that region.

## CI cost

A new package model has no `zz_stg_*` copy, so kipptaf CI cannot resolve the new
source until one exists. Seed it with
`dbt build --select int_powerschool__student_course_grades_spine --target staging`
in `kippnewark`, `kippcamden`, and `kipppaterson`, one at a time; parallel runs
across projects exhaust BigQuery's `INFORMATION_SCHEMA.simple_rate.user` quota.
That writes shared staging tables and needs direct user authorization in the
turn before each call.

## Documentation

No published page in the `mkdocs.yml` nav describes this model's internals. The
package model gets a full properties yml with a description for every column,
sourced from the consumer's yml where the column already exists there. The
consumer's yml keeps its descriptions unchanged, since its contract is
unchanged.
`docs/superpowers/plans/2026-07-07-gradebook-grades-gpa-tableau-rebuild.md` and
`docs/superpowers/plans/2026-08-01-prior-year-backfill-and-category-drivers.md`
name the moved CTEs; they are historical plans and stay as written.

## Not in scope

- Dropping the 7 contract columns no worksheet reads. Contract change, separate
  decision.
- Exposure drift: the workbook also reads `rpt_tableau__gradebook_audit` and
  `rpt_tableau__gpa_goal_progress`, which the `academic_gradebook_health_suite`
  exposure does not list. One-line yml fix, separate PR.
- The student-grain GPA joins in `student_roster`.
- Deleting the #4687 reconstruction. It moves; it does not die here.
- The `base_powerschool__*` compatibility passthroughs and the #3999 wrapper
  sweep.
- Miami, in any form. Ratified on #4996.
