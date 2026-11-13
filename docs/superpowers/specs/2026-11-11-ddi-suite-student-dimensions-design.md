# DDI Suite student dimensions in Cube: design

Issue: #6372. Hub: #6192. Deferred piece: #6373 (`standard_domain`).

## Why

The DDI Suite must be in Cube by Nov 13. After the bucket work (#6280, #6305),
the DDI Suite workbook still uses student and homeroom dimensions that
`student_assessment_scores_view` does not have. This PR adds every remaining one
the workbook's sheets use, except `standard_domain` (#6373).

## Goals

- Every dimension below is a member of `student_assessment_scores_view`.
- Each member returns what the DDI Suite shows today, so a validation comparison
  can match the dashboard, except for the differences listed under _Differences
  to accept_.

## Non-goals

- Fields no DDI Suite sheet uses, even when the extract carries them:
  `self_contained_status`, `is_exempt_iready`, i-Ready EOY proficiency, MTSS
  enrollment, Magoosh.
- Other views. The members go on `student_assessment_scores_view` only.
- Fixing the dashboard's own rules (for example, NJ Tutoring reading today's
  date). Cube copies them; a fix to both is a separate change.
- Measures and goals (PR D), i-Ready lessons (deferred), walkthroughs (out of
  scope).

## Anti-goals

- A student x subject table. Per-subject flags are ELA/math column pairs, so no
  join runs at subject grain and enrollment counts cannot double.
- Values "as of the assessment date". The user decided to copy the dashboard: 1
  value per student per school year.

## Constraints

- #6305 (`bucket_subject` and `bucket`) merges before workstream 4. Workstream 4
  reads `bucket_subject` and sits next to `bucket`.
- Marts read domain `int_` models only (A1). Cube cubes read 1 mart each.
- New student-level columns carry `config.meta.contains_pii: true`, like the
  other status columns.

## Evidence for scope

Source: the local DDI Suite workbook copy (Nov 5,
`~/.cache/cube-validation/ddi_suite/ddi_suite.twb`), all 77 worksheets, with
calculated fields traced to the extract columns they read. Sheet counts below
are worksheets that reference the column directly or through a calculation. 15
calculation references had no definition in the file, so a few more columns may
hide behind them.

The workbook reads 2 extracts: `rpt_tableau__ddi_dashboard` (the "DDI extract")
and `rpt_tableau__assessment_dashboard` (the "assessment extract"). Most flags
appear on sheets from both.

## What gets built

5 workstreams, easiest first. Workstream 4 goes last because it waits on #6305.

### 1. Reuse: nothing to build

The assessment extract renames 2 columns that Cube already has.

| Workbook column                      | Sheets | Cube member              |
| ------------------------------------ | ------ | ------------------------ |
| `module_number` (assessment extract) | 21     | `module_code`            |
| `is_normed_scope`                    | 2      | `is_internal_assessment` |

`rpt_tableau__assessment_dashboard` selects `d.module_code as module_number` and
`asr.is_internal_assessment as is_normed_scope`. Record both mappings in the
validation spec so comparisons use these members.

### 2. School week: Cube YAML only

`week_start_monday` (22 sheets) is the PowerSchool school week. The `dates` cube
already has `school_week_start_date` and `school_week_end_date`. Add both to the
`student_assessment_scores.dates` include on `student_assessment_scores_view`.
This moves the school week out of PR D; update the PR D plan on #6192.

### 3. Per-student flags and homeroom: dbt plus Cube

| Workbook field                        | Sheets                                   | Dashboard rule today                                                                                                                                                      |
| ------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SIPPS (`is_sipps`)                    | 35                                       | Enrolled in course `SEM01099G1` this school year and not dropped                                                                                                          |
| NJ Tutoring (`tutoring_nj`)           | 16                                       | True only while today's date is inside the student's PowerSchool "Tutoring" program dates; the workbook shows "Tutored" / "Not Tutored"                                   |
| Self-Contained (`is_pathways`)        | 2 as a filter, 13 through `% Completion` | Has a self-contained special program in PowerSchool this school year; NJ only, null in Miami                                                                              |
| Homeroom name (`team`)                | 32                                       | `advisory_name`: NJ, the letters in the homeroom section number, else the homeroom teacher's last-first name; Miami, the Focus course period short name, else the teacher |
| Homeroom section (`homeroom_section`) | 4                                        | `advisory_section_number`: the homeroom section number                                                                                                                    |

The assessment extract selects `co.advisory_name as team`; the DDI extract
selects `co.team as homeroom_section`, where `int_extracts__student_enrollments`
defines `team` as `advisory_section_number`. Both come from the same homeroom
pick: 1 per student, school year and school.

dbt: add 5 columns to `dim_student_enrollment_status`, read from
`int_extracts__student_enrollments` (which carries all 5 today), joined on
`student_enrollment_key` built with the `student_enrollment_key` macro, the way
the `section_504` CTE builds it:

- `is_sipps`, `is_tutoring`, `is_self_contained`
- `advisory_name`, `advisory_section_number` (names are the builder's; avoid
  KIPP-specific words under R2)

Cube: add 5 members to the `student_enrollment_status` cube and include them on
`student_assessment_scores_view` through the existing
`student_enrollment_status` join path. `is_tutoring` stays boolean; the
"Tutored" labels are workbook display.

### 4. Per-subject flags: dbt plus Cube, after #6305

None of these is derived from buckets. They share only the subject mapping:
`bucket_subject` decides whether an assessment is ELA or math.

| Workbook field                    | Sheets | Dashboard rule today                                                                                                 |
| --------------------------------- | ------ | -------------------------------------------------------------------------------------------------------------------- |
| Low 25 (FL) (`is_low_25_fl`)      | 35     | Last spring's FAST PM3 percentile rank in the subject below 25.5 (`int_assessments__fast_previous_year`); Miami only |
| Prior-year state test proficiency | 31     | Last year's annual state test proficiency in the subject (`int_assessments__state_scores`), else `No Test`           |
| DIBELS most recent composite      | 35     | Latest DIBELS composite level this school year; Reading only; else `No Composite Score Available`                    |

dbt: 5 columns on `dim_student_enrollment_status`, read from
`int_extracts__student_enrollments_subjects` (1 row per stint per subject; pick
the subject by `discipline`):

- `is_ela_low_25`, `is_math_low_25`
- `ela_state_test_proficiency`, `math_state_test_proficiency`
- `dibels_most_recent_composite` (Reading only; no math column)

Cube:

- 5 private members on the `student_enrollment_status` cube, 1 per column.
- 3 public members on the `student_assessment_scores` cube, next to `bucket`,
  each a `CASE {student_assessments.bucket_subject}` over the pair:
  - `is_low_25`: Reading takes `is_ela_low_25`, Math takes `is_math_low_25`.
  - `state_test_proficiency`: Reading and Math take their columns.
  - `dibels_most_recent_composite`: Reading takes the column, Math returns
    `No Composite Score Available`, other subjects null.
- Other `bucket_subject` values (and null) return null.
- `student_assessment_scores_view` gets the 3 public members only.

The dashboard picks the subject by the student's course, not the assessment: the
DDI extract by the credit type of the student's latest course in the
assessment's subject; the assessment extract by `subject_area` (`Text Study` or
`Mathematics` only) below grade 9 and by course credit type from grade 9 up. The
user chose `bucket_subject` anyway, so the flags and `bucket` always agree on
subject. The gaps this leaves are under _Differences to accept_.

## Validation

On the DDI Suite validation branch (#5668), add comparisons for the sheets that
filter or split by each new member, each with a `rows:` block. Proofs run
against the PR build until the dbt half lands in production.

## Differences to accept

- **Miami subject flags (#6191).** Both extracts find a score's subject through
  the student's section, matched on `studentid`, which is null on every Miami
  row. So the DDI extract leaves Low 25, DIBELS and prior-year state test blank
  for every Miami row, and the assessment extract leaves them blank for Miami
  grades 9-12. Cube fills them. Low 25 is Miami only, so on DDI-extract sheets
  the dashboard's Low 25 filter matches no one today.
- **K-8 subjects outside `Text Study` and `Mathematics` (#6191).** For example,
  K-8 `Algebra I` scores get no subject flags in the assessment extract, but
  `bucket_subject` maps them to Math, so Cube fills them.
- **Per stint vs per year.** The DDI extract joins the subject flags with
  `rn_year = 1` (1 stint per year). The flags are school-year values, so every
  stint in a year should carry the same value; a student with 2 stints in
  different schools could differ.
- **NJ Tutoring reads today's date**, so its value for any row changes when the
  status dim rebuilds, and every past year reads false. Same as the dashboard.

## Decided by the user

- Scope: only dimensions DDI Suite sheets use.
- Copy the dashboard's current behavior, not the assessment date.
- All 5 workstreams in 1 PR.
- `is_current_week` (1 sheet): not built. It is a Tableau design artifact; MCP
  users have other ways to get the current week.
- `standard_domain` (2 sheets): deferred to #6373.
- Subject flags as ELA/math pairs: 5 dbt columns, 3 view members.
- Subject picked by `bucket_subject`, accepting the #6191 differences.
- Homeroom: copy `advisory_name` and `advisory_section_number` from the extract
  onto `dim_student_enrollment_status` (exact match), not from the marts'
  current homeroom.

## Claude's calls (open to change)

- Column and member names above.
- 1 Reading-only DIBELS column instead of a pair.
- `is_tutoring` as boolean, not text.
- The ELA/math pair members stay private in Cube; only the assessment view needs
  the picked members. (#6305 makes `ela_bucket` and `math_bucket` public on 4
  views; these differ on purpose.)
- The new members stay out of the `proficiency_rollup` pre-aggregation, like
  `is_504` (#6211). A query using them reads the fact directly.
- `course_teachernumber` (10 sheets) needs nothing: it feeds only the
  Walkthroughs branch of "Is Mastery Int - Custom", and walkthroughs are out of
  scope.
- Workstream 4 is built last. If #6305 has not merged by then, stop and ask
  before stacking on its branch.

## Left to the builder

- Descriptions for the dbt columns and their Cube twins (`TWINS` in
  `tests/cube/test_cube_schema.py`), and `ai_context` where usage needs saying.
- Exact column and member names for the homeroom pair.
- Folder placement on the view.
