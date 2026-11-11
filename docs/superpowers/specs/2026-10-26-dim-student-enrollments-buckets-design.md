# Add ELA and math buckets to `dim_student_enrollments`

Refs #6145.

## Intent

Analysts break down assessment results (internal, normed, state, and college
entrance) and sometimes ADA by a student's ELA and math bucket. Today the bucket
exists only in the dashboard extracts, as `nj_student_tier` on
`int_extracts__student_enrollments_subjects`, so Cube cannot filter or group by
it. Putting the bucket on `dim_student_enrollments` gives every Cube view that
joins the enrollment cube a bucket slicer.

## Goals

- `ela_bucket` and `math_bucket` on `dim_student_enrollments`, one value per
  enrollment row, following the rule below.
- Miami's 2024-25 and 2025-26 buckets, stored in the frozen PowerSchool archive,
  reach `int_students__bucket_assignments`.
- Both columns exposed in Cube.

## Non-goals

- Changing the dashboards' rule. `int_extracts__student_enrollments_subjects`
  keeps filling `Bucket 4` in every year. The dashboards change only because the
  bucket model gains Miami's archive rows: Miami students get their stored
  bucket in 2024-25 and 2025-26 instead of `Bucket 4`.
- Mid-year history. The dimension carries each student's latest bucket for the
  year. In 2025-26, 16 of about 5,700 students changed ELA bucket and 38 of
  about 5,400 changed math bucket.

## Anti-goals

- A bucket that silently doubles counts in Cube. Anything that adds rows per
  enrollment fails this.
- A bucket label in a year before the 4-bucket model existed.

## The rule

| Case                                      | `ela_bucket` / `math_bucket` |
| ----------------------------------------- | ---------------------------- |
| `academic_year` >= 2025, bucket stored    | the stored bucket            |
| `academic_year` >= 2025, no bucket stored | `Bucket 4`                   |
| `academic_year` < 2025                    | null                         |
| `grade_level` = 99 (graduate placeholder) | null                         |

The 4-bucket model started in 2025-26 (`academic_year` 2025). Students with no
stored bucket from 2025-26 on are `Bucket 4`. That includes grade 12, which is
not bucketed, and current-year placements not yet entered. The user confirmed
both.

The names keep "bucket" on purpose. Staff call it a bucket, and Ed-Fi and CEDS
have no matching concept, so the mart rubric's R2 (no KIPP-specific language)
yields here. `nj_` is dropped because Miami has buckets too.

## Approaches

- **A. Two columns on the dimension, rule in the dimension.** Picked. Smallest
  change, covers ADA, and matches the bucket model's documented contract that
  consumers apply `Bucket 4`. Cost: the `Bucket 4` fill lives in 2 places with
  different start years, the dimension and the dashboards' extract. That is
  intended while the dashboards keep their rule.
- **B. A year-grain domain model that owns the rule, read by the dimension.**
  Pays off only if the dashboards adopt the same rule. Until then it is an extra
  model with 1 reader.
- **C. The bucket on each assessment fact, matched to the score's subject.**
  Removes the chance of reading the wrong subject's bucket, but touches every
  assessment fact, each with its own subject mapping, and does nothing for ADA.
- **Dropped: a long table, 1 row per enrollment and subject.** In Cube it
  doubles every enrollment unless a subject filter is set (anti-goal 1).

## Design

### Miami archive into the spenrollments union

- Declare `int_powerschool__spenrollments` under `kippmiami_powerschool` in
  `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`, with the same
  Dagster asset-key meta as its siblings.
- Add it to the kipptaf `int_powerschool__spenrollments` union. Every kipptaf
  read of the Miami archive goes through a cross-region union like this one.
- The 5 other consumers of the union are unaffected. Each joins on `studentid`
  plus `_dbt_source_project`, and Miami rows in
  `int_extracts__student_enrollments` have a null `studentid` in every year.

### `int_students__bucket_assignments`

- The PowerSchool branch resolves `student_number` by joining
  `int_extracts__student_enrollments` on `studentid`. That join drops every
  Miami archive row, so Miami needs another `studentid` to `student_number`
  path.
- The Miami archive branch and the Focus branch must not overlap on
  `academic_year`. The model's grain test catches an overlap.
- Add a Miami archive input to the existing unit test.
- Update the model description to name the archive as a third store.

### `dim_student_enrollments`

- Left join the bucket model twice, once per subject, on `student_number`,
  `academic_year`, and `_dbt_source_project`.
- Apply the rule with 1 `if()` per column. Comment the 2025 literal (S20).
- Add both columns to the properties YAML with `data_type: string`,
  descriptions, and column-level `config.meta.contains_pii: true` (a bucket is
  student-level program placement).
- Add a unit test covering each row of the rule table.
- No key or hash changes.

### Cube

- Add `ela_bucket` and `math_bucket` dimensions to
  `src/cube/model/cubes/students/student_school_enrollments.yml`. The
  descriptions tell analysts to pick the bucket that matches the subject they
  are analyzing.
- Expose them in the views that include the enrollment cube's members:
  `student_assessment_scores_view`, `student_attendance_enrollment_daily_view`,
  `student_attendance_enrollment_periods_view`, and
  `student_section_enrollments_view`.
- Follow the Cube PII conventions for student-level content.

## Verification

- Every Miami 2025-26 bucket student in the archive reaches the bucket model,
  with no duplicates.
- For `academic_year` >= 2025, the dimension's buckets agree with
  `nj_student_tier` in the extract at student, year, and subject grain.
- Before 2025, and on grade 99 rows, both columns are null.
- A Cube query on an assessment view filtered by `math_bucket` returns rows.

## Left to the builder

- The `studentid` to `student_number` path for Miami archive rows. The kipptaf
  `int_powerschool__ada` union maps 1,026 of 1,027 Miami 2025-26 bucket students
  with no duplicates. The archive's `base_powerschool__student_enrollments` maps
  all 1,027, but `sources-kippmiami.yml` deliberately omits archive enrollment
  stints, so using it needs a reason. Acceptance: every student maps.
- Cube titles and which views list the new members explicitly.

## Revision 2026-10-29

The DDI Suite builder inventory
([#6192](https://github.com/TEAMSchools/teamster/issues/6192)) adds 1 column to
this design and corrects 1 non-goal.

### `bucket_subject` on `dim_assessments`

DDI Suite filters by 1 "Student Tier" field on 32 sheets, and that filter
applies each score's own subject. Separate `ela_bucket` and `math_bucket`
columns cannot do that in 1 filter when a query mixes subjects.

- Add `bucket_subject` to `dim_assessments`: `Reading`, `Math`, or null, from
  the assessment's subject.
- Add a `bucket` dimension to the `student_assessment_scores` cube. It reads
  `ela_bucket` when `bucket_subject` is `Reading` and `math_bucket` when it is
  `Math`.
- The mapping lives in dbt because `academic_subject` is an open vocabulary, and
  1 value carries a trailing space. A CASE list in Cube YAML would drift.
- The mapping matches the dashboards: K-8 `Text Study` and `Mathematics`, and
  the high-school English and math courses that the dashboards reach through
  credit types `ENG` and `MATH`. Middle-school `Algebra I` gets no tier in the
  dashboards today
  ([#6191](https://github.com/TEAMSchools/teamster/issues/6191)). Decide its
  mapping in the PR and record the choice.
- No Cube dimension in `src/cube/model` reads a joined cube's column yet.
  Compile the `bucket` dimension before the Cube PR relies on it.

A separate bucket cube at student x year x subject gives the same numbers. It
was set aside because it needs a new key on the scores fact and does nothing for
ADA.

### Miami in the dashboards

The first non-goal says the dashboards gain Miami's archived buckets. Only the
K-8 rows of `rpt_tableau__assessment_dashboard` do. `rpt_tableau__ddi_dashboard`
and the grade 9-12 rows of `rpt_tableau__assessment_dashboard` leave Miami's
tier blank, because their tier join reaches the student's section through
`studentid`, which is null for Miami.
[#6191](https://github.com/TEAMSchools/teamster/issues/6191) fixes the extracts.
Until then, Cube shows Miami's stored bucket, and the DDI Suite validation
records the difference as accepted.

### Verification added

- A simulation of the 2 Module Dashboard bucket sheets for 2026-27 Literacy
  matched the dashboard in 93 of 105 cells. Every other cell traces to Miami's
  blank dashboard tier or to score rows that only 1 side has. Where both sides
  have the student, the bucket matched every time. Rerun the comparison on the
  validation branch after the Cube PR.

## Revision 2026-11-09

The review of [#6280](https://github.com/TEAMSchools/teamster/pull/6280)
(analytics engineering) moves the buckets out of `dim_student_enrollments` into
a status dimension, the pattern `dim_student_ell_status` and
`dim_student_iep_status` follow. This replaces approach A, the `ela_bucket` and
`math_bucket` columns on `dim_student_enrollments`, and withdraws the "Mid-year
history" non-goal.

Why: latest-wins keeps 1 bucket per student, year, and subject, so it loses
mid-year changes. In 2025-26, 54 of 12,888 student, subject, and year groups
held 2 or more buckets. A status dimension keeps every span, and the rule that
turns spans into 1 bucket per enrollment gets 1 home.

### Bucket assignments, by span

- `int_students__bucket_assignments` moves to 1 row per stored assignment:
  `student_number`, `_dbt_source_project`, `academic_year`, `subject`, `bucket`,
  `bucket_store`, `assignment_date`, and `exit_date`. It stays the 1 home that
  decodes the 3 stores (NJ PowerSchool programs, the Miami archive, and Miami
  Focus groups).
- [#6349](https://github.com/TEAMSchools/teamster/pull/6349) already put the
  Miami archive in the spenrollments union and keyed the PowerSchool branch on
  the `student_number` that the package model now carries. That replaces this
  design's archive source entry, its union change, and its `studentid` to
  `student_number` path through `int_powerschool__ada`.
- The latest-wins pick moves to `int_students__bucket_assignments_rollup`, at
  the old grain (`academic_year` x `_dbt_source_project` x `student_number` x
  `subject`). `int_extracts__student_enrollments_subjects` reads the rollup, so
  `nj_student_tier` and the dashboards do not change.

### `dim_student_bucket_status`

- 1 row per student, subject, and span, clipped to the enrollment stint it
  overlaps, as in `dim_student_iep_status`.
- A span starts on `assignment_date` and ends the day before `exit_date`, or on
  `9999-12-31` when there is no exit date.
- A span joins a stint on `student_number`, `_dbt_source_project`, and
  `academic_year`, plus date overlap. Joining on `academic_year` keeps a span
  with no exit date from reaching the next year's stints.
- Columns: `student_bucket_status_key` (from `student_number`,
  `_dbt_source_project`, `subject`, and the clipped start date), `student_key`,
  `student_enrollment_key` (through its key macro), `_dbt_source_project`,
  `subject`, `bucket`, `bucket_store`, `effective_date_start_key`,
  `effective_date_end_key`, and `is_current`.
- `student_enrollment_key` is not unique here. Consumers read the rollup below,
  never this dimension, when they need 1 bucket per enrollment.
- `config.meta.contains_pii: true` on `bucket`, as on the old columns.

### The rollup in `dim_student_enrollment_status`

`ela_bucket` and `math_bucket` move to `dim_student_enrollment_status`, 1 value
per enrollment stint. This rule needs the DDI Suite owner's sign-off:

| Case, per stint and subject                            | `ela_bucket` / `math_bucket`               |
| ------------------------------------------------------ | ------------------------------------------ |
| `academic_year` >= 2025, grade not 99, 1 or more spans | the bucket of the latest span in the stint |
| `academic_year` >= 2025, grade not 99, no span         | `Bucket 4`                                 |
| `academic_year` < 2025                                 | null                                       |
| `grade_level` = 99 (graduate placeholder)              | null                                       |

"Latest" means the greatest `effective_date_start_key`, as the IEP rollup does.
The dashboard keeps the latest bucket per student and year instead, so the 2
agree for a student with 1 stint in the year. For a student with 2 stints, the
earlier stint keeps the bucket that applied during it. On grade 99 rows, the
dashboard shows `Bucket 4` and Cube shows null. The DDI Suite validation records
both as accepted differences.

### Cube

- `ela_bucket` and `math_bucket` move from the `student_school_enrollments` cube
  to the `student_enrollment_status` cube, with the same names. The member names
  in the DDI Suite validation file do not change.
- `student_section_enrollments_view` gains the
  `student_school_enrollments.student_enrollment_status` join path. The other 3
  views already include it.
- `student_assessment_scores.bucket` reads `student_enrollment_status` in place
  of `student_school_enrollments`.
- The twins move to `dim_student_enrollment_status`.
- The Cube pull request,
  [#6305](https://github.com/TEAMSchools/teamster/pull/6305), carries these
  changes.

### Verification for this revision

- Every 2025-26 and later stored assignment reaches `dim_student_bucket_status`,
  or is counted as falling outside every stint of its year.
- For students with 1 stint in the year, the rollup equals the old rule's value
  for every stint from 2025-26 on.
- Unit tests cover each row of the rule table, a span clipped by 2 stints, and a
  span with no exit date.
- The DDI Suite comparisons on the validation branch run again on the new
  members.

### Left to the builder

- Whether to merge consecutive spans that hold the same bucket into 1 span, as
  `dim_student_iep_status` merges islands. The rollup returns the same value
  either way.
- What to do when 2 assignments for the same student and subject share an
  `assignment_date`. Today's order (active first, then latest exit, then bucket)
  is the starting point.
