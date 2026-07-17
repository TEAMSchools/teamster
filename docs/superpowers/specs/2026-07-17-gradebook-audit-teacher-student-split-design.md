# Gradebook Audit: Teacher/Student Split Design

## Background

`rpt_tableau__gradebook_audit` currently mixes two different concerns in one
Tableau-facing table: teacher/section-level gradebook compliance (assignment
counts, point values, missing scores) and student-level grade anomalies (a bad
quarter grade, a missing EOQ comment). The student-level branch carries full
student PII (name, student number) into a Tableau-facing report.

This design splits those concerns: student-level flag data moves to a new Google
Sheet extract for ops follow-up, and the Tableau-facing report becomes
teacher/section-only, with zero student PII, redesigned around boolean flag
columns instead of filtered UNION branches.

Full pipeline reference:
[`docs/reference/gradebook-audit-data-model.md`](../reference/gradebook-audit-data-model.md).
Tracked under
[GitHub issue #3908](https://github.com/TEAMSchools/teamster/issues/3908) — no
new issue for this work; continue updating #3908 as it lands.

## Goals

- Remove all student PII from `rpt_tableau__gradebook_audit`.
- Move student-level grade/comment flags to a new Google Sheet extract for ops
  review.
- Redesign the teacher-facing report around always-present boolean flag columns
  (not enough assignments, grade above 100 anywhere in the section, grade below
  70 with no comment anywhere in the section) instead of the current
  three-branch filtered UNION.
- Surface actual assignment counts entered per gradebook category, regardless of
  flag status, alongside the existing expected counts.
- List individual assignments that fail the "no flags" bar, without exposing
  which specific rule they violated (that level of detail is exactly what this
  redesign is moving away from).
- Redefine "healthy gradebook" as two parallel boolean columns — one counting
  all flags, one excluding the EOQ comment-missing flag — so Tableau can
  parameter-toggle between them without needing two copies of every row.
- Fix a known data gap: student-level rows currently include enrollments for
  sections that `int_extracts__course_schedule_by_term`'s
  `section_quarter_count >= 2` filter excludes (single-quarter/trimester
  sections), so a student can be flagged for a "course" that has no
  corresponding teacher/section presence anywhere else in the pipeline. Fixed by
  scoping student data to only sections that exist in
  `int_extracts__course_schedule_by_term` — no explanatory column, just silent
  exclusion.

## Non-goals

- `rpt_tableau__gradebook_es_comments` (the ES-only EOQ-comment check) is
  unrelated and untouched by this work.
- No per-rule "reason" text is added anywhere (not for flagged assignments, not
  for flagged students) — this redesign's whole point is aggregated boolean
  signals, not granular rule-level detail. `assignment_has_flags` stays a single
  collapsed boolean; the individual rule booleans computed in
  `int_powerschool__gradebook_assignment_scores_rollup`
  (`assign_max_score_not_10`, `assign_score_above_max`, etc.) are not surfaced
  downstream of the rollup.
- No new dbt model beyond the two described below — this explicitly replaces a
  4-model sketch (two intermediates, two reports) with two total models.
- No changes to `int_powerschool__gradebook_assignment_scores_rollup`,
  `int_powerschool__gradebook_assignments_scores`, or the summer-toggle
  mechanism itself (this design's own toggle points follow the same pattern
  already documented in the gradebook-audit skill).

## Architecture

Two models, replacing four current ones
(`int_tableau__gradebook_audit_flags_calculations` and
`rpt_tableau__gradebook_audit` reworked; no other new files):

```text
int_extracts__course_enrollments_by_term ──┐
int_extracts__course_schedule_by_term ─────┼──► rpt_gsheets__gradebook_audit_student_flags
quarter grade/comment data ─────────────────┘         │
                                                        │ (read for section-level
                                                        │  "any student flagged" booleans)
                                                        ▼
int_extracts__course_schedule_by_term ──┐
int_powerschool__u_expectations_qtd_unpivot ┼──► rpt_tableau__gradebook_audit
int_powerschool__gradebook_assignment_scores_rollup ┘
```

`int_tableau__gradebook_audit_flags_calculations` is disabled once
`rpt_tableau__gradebook_audit` no longer depends on it — matching how the AY
2026-2027 redesign already retired several predecessor models
(`int_tableau__gradebook_audit_teacher_scaffold`, `_assignments_teacher`, etc.)
by folding their logic into successor models.

**Note on layering:** `rpt_tableau__gradebook_audit` reads directly from
`rpt_gsheets__gradebook_audit_student_flags` via `ref()` — an
`rpt_`-depends-on-`rpt_` dependency. This is slightly unusual (the documented
convention is about keeping `int_` models away from external tools, not about
rpt-to-rpt refs specifically) but is the only way to land on exactly two models.
Accepted tradeoff for this design.

## Model 1: `rpt_gsheets__gradebook_audit_student_flags`

**Purpose:** flagged-student rows for ops review via an external Google Sheet.
Also the upstream source `rpt_tableau__gradebook_audit` reads for its
section-level "any student flagged" booleans.

**Grain:** one row per (`_dbt_source_project`, `academic_year`, `studentid`,
`sectionid`, `quarter`) — flagged rows only (see filter below).

**Source logic:**

- Base population: `int_extracts__course_enrollments_by_term`, carrying the same
  filters the current `student_course` branch of
  `int_tableau__gradebook_audit_flags_calculations` applies today (
  `rn_year = 1`, `enroll_status = 0`, `not is_out_of_district`,
  `school_level_alt != 'ES'`, `_dbt_source_project != 'kippmiami'`,
  `exclude_from_gpa = 0`, `quarter_start_date <= current_date`, plus the
  `academic_year` summer-toggle filter).
- **New: inner join to `int_extracts__course_schedule_by_term`** on
  (`_dbt_source_project`, `sectionid`, `quarter`, `academic_year`). This is the
  orphan-scoping fix — a student's course only produces a row here if the
  section also exists in the schedule model. No reason/diagnostic column is
  added; rows that don't match simply don't appear.
- Grade/comment source: the same `quarter_course_grades` union (
  `base_powerschool__final_grades` for the current year,
  `stg_powerschool__storedgrades` for the prior year during the summer toggle)
  already used by the current model.
- Two boolean flag columns, computed once per row (mutually exclusive by
  definition — a grade can't be both above 100 and below 70):
  - `qt_percent_grade_greater_100`
  - `qt_grade_70_comment_missing`
- Final filter: keep only rows where at least one of the two booleans is true.

**Columns:** student identity (`studentid`, `student_number`, `student_name`,
`grade_level`), section/course identity (`sectionid`, `course_number`,
`course_name`, `section_number`, `external_expression`, `section_or_period`),
teacher identity (`teacher_number`, `teacher_name`, `teacher_employee_number`),
school/region (`schoolid`, `school`, `region`, `school_level`), term (`quarter`,
`semester`, `quarter_start_date`, `quarter_end_date`), the raw
`quarter_course_percent_grade` and `quarter_comment_value`, and the two boolean
flags.

**Tests:** `dbt_utils.unique_combination_of_columns` on (`_dbt_source_project`,
`academic_year`, `studentid`, `sectionid`, `quarter`).

## Model 2: `rpt_tableau__gradebook_audit` (reworked)

**Purpose:** teacher/section-facing gradebook compliance report. Zero student
PII.

**Grain:** floor of one row per (`_dbt_source_project`, `academic_year`,
`schoolid`, `teacher_number`, `sectionid`, `quarter`,
`assignment_category_code`) — i.e. exactly four rows per section per quarter
(W/H/F/S categories), present even when nothing is flagged. Each assignment that
fails the "no flags" bar for that category adds one additional row, with
assignment-identity columns (`assignmentid`, `assignment_name`, `duedate`,
`scoretype`, `totalpointvalue`) populated on the detail row and null on the
category-summary row — the same "union of differently-shaped branches, same
column set" pattern the current model already uses for its anchor rows. A
teacher with zero flags anywhere has exactly `(number of sections) × 4` rows for
the quarter; no separate anchor row concept is needed.

A `row_type` column (`'category_summary'` or `'assignment_detail'`)
distinguishes the two shapes explicitly, so Tableau can filter to one or the
other rather than inferring it from `assignmentid` being null. The
count/expectation columns (`expectation`, actual assignment count,
`not_enough_assignments`) are populated **only on `category_summary` rows** and
null on `assignment_detail` rows — these are category-level facts, and repeating
them on every detail row would make a naive `SUM` in Tableau over-count them
once per extra flagged assignment. This is the opposite choice from the
section-level flag/health booleans below, which are deliberately broadcast onto
every row (including detail rows) because those are meant to be readable off any
single row without a self-join.

**Structure (CTEs within the single model):**

1. **Category summary** — from `int_extracts__course_schedule_by_term` joined to
   `int_powerschool__u_expectations_qtd_unpivot` (one row per section × quarter
   × category) left joined to
   `int_powerschool__gradebook_assignment_scores_rollup` aggregated up to
   category grain. Produces, per category row: `expectation` (expected count),
   `assignments_entered_count` (actual count of assignments entered regardless
   of flag status), and `not_enough_assignments` (boolean;
   actual-count-of-non-flagged assignments below expectation — same comparison
   the current `expected_assign_count_not_met` uses, renamed for the
   boolean-column scheme).
2. **Assignment detail** — same join chain, but selecting individual assignment
   rows where `assignment_has_flags` is true, with identity columns populated.
3. **Combined** — `UNION ALL` of (1) and (2), tagging each side with its
   `row_type` (`'category_summary'` or `'assignment_detail'`).
4. **Student flags aggregate** — reads
   `rpt_gsheets__gradebook_audit_student_flags`, grouped to
   (`_dbt_source_project`, `sectionid`, `quarter`) grain, computing
   `has_grade_above_100` and `has_grade_below_70_no_comment` via `count(*) > 0`
   per flag type (no PII carried through — only the booleans and the join keys).
5. **With section flags** — left join (3) to (4) on (`_dbt_source_project`,
   `sectionid`, `quarter`), broadcasting the two student-derived booleans onto
   every row (all 4 category rows, plus any assignment-detail rows) for that
   section/quarter. These two columns are intentionally identical across all
   rows for a given section — they are section-level facts, not category-level
   ones.
6. **Health calc** — aggregates over (5) at (`_dbt_source_project`,
   `academic_year`, `schoolid`, `teacher_number`, `quarter`) grain (across _all_
   of a teacher's sections, not just one), producing two boolean columns:
   - `is_healthy_gradebook_all_flags` — false if any of
     `not_enough_assignments`, `has_grade_above_100`, or
     `has_grade_below_70_no_comment` is true anywhere for that teacher/quarter.
   - `is_healthy_gradebook_excl_comments` — same, but
     `has_grade_below_70_no_comment` is excluded from the check (still present
     as a column on every row, just not counted toward this health definition).
     A Tableau parameter selects which column to read.
7. **Final select** — join (5) to (6) on (`_dbt_source_project`,
   `academic_year`, `schoolid`, `teacher_number`, `quarter`), broadcasting the
   two health columns onto every row for that teacher/quarter.

**Columns:** all existing teacher/section/school identity columns from the
current model (region, school, section, teacher — including
`teacher_employee_number`, `manager_employee_number`, etc.), `row_type`,
category dimension (`assignment_category_code`, `assignment_category_name`,
`assignment_category_term`, `expectation` — nullable, populated on
`category_summary` rows only), assignment-detail columns (nullable, populated on
`assignment_detail` rows only), the three flag booleans
(`not_enough_assignments` — nullable, populated on `category_summary` rows only;
`has_grade_above_100`, `has_grade_below_70_no_comment` — broadcast on every
row), the two health booleans (broadcast on every row), and
`assignments_entered_count` (nullable, populated on `category_summary` rows
only).

**Tests:** `dbt_utils.unique_combination_of_columns` on (`_dbt_source_project`,
`academic_year`, `sectionid`, `quarter`, `assignment_category_code`,
`assignmentid`) — category-summary rows are unique per category with a null
`assignmentid`; assignment-detail rows are unique per real `assignmentid`.

## Validation plan

- Dev build both models; confirm both uniqueness tests pass.
- Confirm the row-count floor empirically: for a teacher with zero flags in a
  quarter, `count(*) = sections × 4` exactly.
- Confirm the orphan-scoping join actually removes the previously-identified
  gap: re-run the `section_quarter_count` orphan check from the PR review (83
  sections / ~800 students in AY2025) against the new model and confirm zero
  remain.
- Spot-check `is_healthy_gradebook_all_flags` vs.
  `is_healthy_gradebook_excl_comments` disagree only on rows/teachers whose sole
  flag is `has_grade_below_70_no_comment`.
- Confirm `rpt_gsheets__gradebook_audit_student_flags` row count matches the
  count of true values across both flags in the pre-filter population (no rows
  lost or duplicated by the filter).
