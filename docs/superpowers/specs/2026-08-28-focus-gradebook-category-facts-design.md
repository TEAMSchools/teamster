# Focus gradebook and category grades into the kipptaf grades facts

Design for [#5010](https://github.com/TEAMSchools/teamster/issues/5010).
Measured against prod on 2026-08-28.

## Problem

`fct_grades_assignments` and `fct_grades_category` hold zero Miami rows for
AY2026. Both inner-join a source that unions only the district PowerSchool
packages, and Miami left that package at the Focus cutover, so its archive stops
at AY2025. No join-key change can produce a row that the source does not hold.

Focus holds the data in `int_focus__gradebook_grades`. It has no kipptaf
wrapper, so nothing reaches the network layer.

## Measurement

### The package model is column-sufficient

`int_focus__gradebook_grades` carries everything both facts need. Nothing here
requires widening it or adding a package model.

| Fact need                            | Source                                                         | Status                                                                                                   |
| ------------------------------------ | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Score and points                     | `points`, `assignment_points`                                  | Present. `possible_points` is null on all 4,764 rows, so `max_points` reads `assignment_points`.         |
| Category and weight                  | `assignment_type_title`, `assignment_type_final_grade_percent` | Present. Titles map 1:1 onto PowerSchool's `storecode_type` domain.                                      |
| Course-period link                   | `course_period_id`                                             | Joins `int_students__course_enrollments.sections_dcid` with 0 orphans on all 4,625 linkable rows.        |
| `academic_year`                      | Not on the model                                               | Derived at kipptaf from `marking_period_id` to `stg_focus__marking_periods.syear`. 0 nulls on the 4,625. |
| Due date                             | `due_date`                                                     | Present.                                                                                                 |
| `is_missing`, `numeric_grade_earned` | No Focus analog                                                | Null, per the `int_students__final_grades` precedent.                                                    |

Per the column-set rule on
[#4985](https://github.com/TEAMSchools/teamster/issues/4985), a change that adds
no columns cannot trigger the
[#4290](https://github.com/TEAMSchools/teamster/issues/4290) deploy race. **This
is one PR.**

### Focus category titles share PowerSchool's domain

| Focus `assignment_type_title` | Scores | PowerSchool `storecode_type` |
| ----------------------------- | ------ | ---------------------------- |
| Formative                     | 2,614  | `F`                          |
| Work Habits                   | 1,436  | `W`                          |
| Homework                      | 618    | `H`                          |
| Summative                     | 96     | `S`                          |

`int_powerschool__category_grades` for AY2026 emits `storecode_type` in `Q`,
`H`, `W`, `F`, `S`. `fct_grades_category` is therefore the
per-gradebook-category percent grade per quarter per section, not a
quarter-versus-exam breakdown as its current description implies.

### The grain finding

`int_focus__gradebook_grades` holds 4,764 rows against 4,673 distinct
`student_gradebook_grade_id`. 91 ids appear twice. All 91 are the same shape: a
student scheduled into 2 course periods that share one assignment. 4 assignments
produce all 91.

The model declares `unique` at `severity: error` on
`student_gradebook_grade_id`, so that test fails against these rows.

**The rows are correct and the test is wrong.** Evidence, in order:

1. Focus's own ERD (`Focus DB Diagram.pdf`, page 18, authored by Focus,
   2026-02-23) gives `gradebook_grades` as `PK id` plus FKs to `student_id`,
   `assignment_id`, `standard_id`, `letter_grade`, `comment_codes`. There is no
   `course_period_id` and no FK to `gradebook_assignments_join_course_periods`.
   Focus's storage grain is student by assignment.
1. Raw `dagster_kippmiami_dlt_focus.gradebook_grades` matches the ERD — the
   staging model drops no relevant column, unlike the case in
   [#4925](https://github.com/TEAMSchools/teamster/issues/4925).
1. All 6 gradebook tables are already in `focus.yaml`. The 4 the ERD names that
   we do not ingest carry no per-score section link: `gradebook_comment_codes`,
   `gradebook_custom_grades`, `gradebook_template_categories`, and
   `gradebook_grade_colors` (which has `course_period_id` but is a teacher's
   per-section color config keyed on `teacher_id`).
1. Reading `gradebook_grades.assignment_id` as the join table's `id` is refuted:
   it matches on 4,625 of 4,673 rows, but **0** of those land on a course period
   the student is scheduled into. The numeric overlap is coincidence between two
   dense integer spaces.
1. Focus's reporting grain is strictly per section.
   `int_focus__report_card_grades` for AY2026 is 1,901 rows, unique on
   `(student_id, course_period_id, marking_period_id)`, with 0 null course
   periods and no cross-course aggregation.
1. For the ambiguous scores, Focus posts a report card grade in **both**
   sections, at a percent consistent with the shared scores. Example: grade id
   `7025719`, marking period 7181, carries 2 scores totalling 20 of 20 in each
   of Homeroom 2nd Grade (151013) and LANG ARTS GRADE 2 (151698), and Focus
   reports 100 percent in both. A score on a multi-section assignment feeds
   every section the student sits in.

PowerSchool stores what Focus derives — `assignmentsectionid` is already per
section, so a PowerSchool student in 2 sections of a shared assignment gets 2
score rows. The fan is PowerSchool parity. `fct_grades_assignments` is a student
by assignment by section fact in both branches.

Using the report card as a tiebreaker was considered and rejected: it resolves
only 29 of the 91 to a single section, and Q1 is in progress, so an unposted
grade is indistinguishable from a section that will never receive one.

### The `-1` points sentinel

192 rows carry `points = -1`. 118 also carry letter grade `A` and 74 carry no
letter grade. Every normally scored row (0 to 100) also carries a letter grade,
so `-1` is not a "graded by letter" marker — it reads as not-yet-graded or
excused. Treated as a numeric score it yields `score_percent = -10` and poisons
every category average that contains it.

### Join keys verified

The enrollment key swap is exactly 1:1 for all 3 NJ regions, so it moves no NJ
row. Distinct counts of `(studentid, schoolid, yearid)` against
`(student_number, schoolid, academic_year)` in
`int_students__student_enrollment_union`:

| Region       | PowerSchool key | Network key |
| ------------ | --------------- | ----------- |
| kippcamden   | 23,862          | 23,862      |
| kippnewark   | 97,966          | 97,966      |
| kipppaterson | 2,076           | 2,076       |

`studentid` and `yearid` are null on all 1,763 Miami AY2026 rows;
`student_number` and `academic_year` are null on none.

`cc_dateleft` is null on 18,582 of 19,398 Miami AY2026 course enrollments (95.8
percent) and on 0 NJ rows, so the PowerSchool date-window join drops nearly
every Miami row as written.

All 19,398 Miami AY2026 course enrollments already resolve in
`dim_student_section_enrollments`, so the FK relationships tests will pass.

## Design

### Model 1 — `focus` package, properties only

`src/dbt/focus/models/intermediate/properties/int_focus__gradebook_grades.yml`:

- Replace the `unique` test on `student_gradebook_grade_id` with
  `dbt_utils.unique_combination_of_columns` on
  `(student_gradebook_grade_id, course_period_id)`.
- Keep `not_null` on `student_gradebook_grade_id`.
- Rewrite the description to state the real grain — one row per score per
  resolved course period — and record why the fan matches Focus's own
  per-section report card rather than being a defect.

No SQL change and no column change, so `dbt clone --target staging` seeds a
schema-correct copy and the corrected test passes against the cloned prod rows.

### Model 2 — kipptaf source entries and wrappers

Add to `src/dbt/kipptaf/models/focus/sources-kippmiami.yml`, each with the
standard dagster `asset_key` meta block:

- `int_focus__gradebook_grades`
- `stg_focus__gradebook_assignments_join_course_periods`

Add the matching `union_relations` passthrough wrappers under
`src/dbt/kipptaf/models/focus/`. Both re-declare `config.meta.contains_pii`,
which does not travel through `source()`.

The second wrapper is what makes the surrogate key work. Its `id` is one row per
assignment per course period — the exact semantics of PowerSchool's
`assignmentsectionid`.

### Surrogate keys — NJ hashes stay byte-identical

`fct_grades_assignments.grades_assignment_key` keeps its 3 inputs unchanged. The
conformed model fills them per branch with true analogs, so no NJ value moves.

| Key input             | PowerSchool branch    | Focus branch                                   |
| --------------------- | --------------------- | ---------------------------------------------- |
| `assignmentsectionid` | `assignmentsectionid` | `gradebook_assignments_join_course_periods.id` |
| `_dbt_source_project` | unchanged             | unchanged                                      |
| `students_dcid`       | `students_dcid`       | `student_id`, Focus's internal student row id  |

The fact reads `students_dcid` from the conformed scores model rather than from
course enrollments. `int_powerschool__gradebook_assignments_scores` already
carries it, so NJ values are unchanged.

`fct_grades_category.grades_category_key` needs no change — `cc_dcid` already
resolves in both branches through `int_students__course_enrollments`.

Neither key is referenced outside its own model and properties file — no Cube
model, no downstream FK — so both are leaf primary keys.

### Model 3 — `int_students__gradebook_assignments_scores`

SIS-neutral, on the `int_students__final_grades` shape. Lives in
`src/dbt/kipptaf/models/students/intermediate/`.

PowerSchool branch reads `int_powerschool__gradebook_assignments_scores`, scoped
by a `focus_academic_year_boundary` CTE with the same
`coalesce(min(academic_year), 9999)` guard the sibling models use, so the frozen
Miami AY2020 to AY2025 archive stays readable.

Focus branch reads the 2 new wrappers, joined to
`int_students__course_enrollments` for `cc_dcid`, `cc_schoolid` and `region`,
and to `stg_focus__marking_periods` for `academic_year`.

| Conformed column            | Focus source                                                       |
| --------------------------- | ------------------------------------------------------------------ |
| `max_points`                | `assignment_points`                                                |
| `points_earned`             | `points`, null when `points < 0`                                   |
| `score_percent`             | `points / assignment_points * 100`, null when `points < 0`         |
| `is_late`                   | `late`                                                             |
| `is_exempt`                 | `exclude_from_average`                                             |
| `is_counted_in_final_grade` | `not assignment_exclude_from_average`                              |
| `is_expected`               | `not exclude_from_average and not assignment_exclude_from_average` |
| `category_name`             | `assignment_type_title`                                            |
| `category_code`             | mapped `storecode_type`, below                                     |
| `duedate`                   | `due_date`                                                         |
| `assignment_name`           | `assignment_title`                                                 |
| `is_missing`                | null — no Focus analog                                             |
| `numeric_grade_earned`      | null — Focus scoring is points-based                               |

The gradebook-audit columns on the PowerSchool model
(`assign_mh_hwf_score_less_5` and siblings) stay out of scope. This model serves
the 2 facts; the audit cluster keeps reading
`int_powerschool__gradebook_assignments_scores` unchanged.

### Model 4 — `int_students__category_grades`

PowerSchool branch reads `int_powerschool__category_grades`, year-scoped the
same way.

Focus branch aggregates `int_students__gradebook_assignments_scores` — Focus
rows only — over `(cc_dcid, category, marking_period)`, reusing the conform work
rather than re-reading the wrapper.

| Conformed column           | Focus derivation                                                   |
| -------------------------- | ------------------------------------------------------------------ |
| `storecode_type`           | category title mapped to `F` / `H` / `W` / `S`                     |
| `storecode_order`          | quarter number from the marking period `short_name`                |
| `storecode`                | `storecode_type` concatenated with `storecode_order`               |
| `reporting_term`           | `RT` concatenated with `storecode_order`                           |
| `quarter`                  | marking period `short_name`                                        |
| `percent_grade`            | `sum(points) / sum(assignment_points) * 100` over scored rows only |
| `is_current`               | current date between the marking period start and end dates        |
| `citizenship_grade`        | null — no Focus analog                                             |
| `percent_grade_y1_running` | null — Focus has no year-to-date rollup                            |

Only `H`, `W`, `F` and `S` are emitted. `Q` rows are the quarter-overall grade,
which already reaches the marts through `int_students__final_grades` and
`fct_grades_term`; duplicating it here would add a second source to the branch
for a number that is already published.

An unmapped category title falls back to the raw title rather than to null, so a
new Focus category surfaces in the fact instead of vanishing from it.

### Model 5 — repoint both facts

Both read the conformed models and `int_students__course_enrollments`.

`fct_grades_assignments`:

- Source swaps to `int_students__gradebook_assignments_scores`.
- Course enrollments swap to `int_students__course_enrollments`.
- The enrollment join swaps `(cc_studentid, cc_academic_year - 1990)` for
  `(students_student_number, cc_academic_year)`. The 1990 offset is a
  PowerSchool convention with no Focus equivalent, and the swap is 1:1 for NJ.
- `asg.duedate < ce.cc_dateleft` becomes
  `asg.duedate < coalesce(ce.cc_dateleft, date '9999-12-31')`. Miami-only in
  effect, since `cc_dateleft` is null on 0 NJ rows.
- `students_dcid` for the key comes from the scores model, not from course
  enrollments.

`fct_grades_category`:

- Source swaps to `int_students__category_grades`.
- Course enrollments swap to `int_students__course_enrollments`.
- The join swaps `(studentid, sectionid, yearid)` for
  `(students_student_number, sections_dcid, cc_academic_year)`.
  `cc_abs_sectionid` and `cc_yearid` are null on every Miami row.

Both fact descriptions lose their "PowerSchool only, Miami is absent"
paragraphs.

## Validation

The quarter is in progress. Miami Q1 runs 2026-08-12 to 2026-10-16, so the
gradebook holds roughly 2 weeks of a 9-week term.

### Full weight now

1. Grain uniqueness on `int_students__gradebook_assignments_scores`,
   `int_students__category_grades`, and both facts.
1. Zero-orphan FK joins from both facts to `dim_student_section_enrollments` and
   `dim_terms`.
1. NJ parity, per model and per region, as `count(*)` plus
   `count(distinct format('%T|%T', ...))` on the key columns, against prod.
1. `grades_assignment_key` byte-identical for all 3 NJ regions.
1. Miami AY2026 rows present in both facts, verified by row count.
1. The Miami archive still readable — AY2020 to AY2025 Miami row counts
   unchanged in both facts.
1. `dbt build --empty` across the descendant graph.
1. After the deploy, compare each rebuilt kipptaf wrapper's stored
   `input_data_version` materialization tag against the upstream's current
   `data_version` before trusting a green build.

### Directional until Q1 closes on 2026-10-16

Any magnitude comparison of Miami against NJ — scores per student, category
percent grade distributions, assignment counts per section. These mature as Q1
fills. They are recorded in the PR body as directional, not as pass or fail
criteria.

## CI

`int_focus__gradebook_grades` changes only its properties file, and the 2 other
package models are unmodified, so `dbt clone --target staging` seeds
`zz_stg_kippmiami_focus` with schema-correct rows. Authorized 2026-08-28: clone,
then `dbt build --select int_focus__gradebook_grades --target staging` so CI
exercises the corrected test.

## Out of scope

- The gradebook-audit cluster. It keeps reading
  `int_powerschool__gradebook_assignments_scores` unchanged.
- `Q` rows in the Focus branch of `fct_grades_category`.
- `student_standard_grades`, still empty upstream.
- `fct_grades_gpa`, shipped separately under
  [#5021](https://github.com/TEAMSchools/teamster/issues/5021).

## Follow-ups found while measuring

- The `DT` versus `DY` marking-period token, recorded as an open external
  dependency on [#4925](https://github.com/TEAMSchools/teamster/issues/4925) and
  on #4997, is answered by the Focus Level 1 certification training document:
  `DT` is the running gradebook grade, `DY` is yesterday's grade, and `E` is an
  exam. Belongs on those issues, not here.
- `fct_grades_category`'s description calls its grain "quarter grades vs exam
  grades". The measured `storecode_type` domain is `Q`, `H`, `W`, `F`, `S` — the
  gradebook categories. Corrected as part of this work.
