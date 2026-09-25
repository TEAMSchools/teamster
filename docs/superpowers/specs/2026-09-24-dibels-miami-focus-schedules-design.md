# Show Miami on the DIBELS dashboard, with Focus ELA schedules

Refs [#5518](https://github.com/TEAMSchools/teamster/issues/5518)

## Revision 2026-09-25: after PR review

GabyRangelB and cbini reviewed the spec on #5519, and the owner settled the open
questions on 2026-09-25. This revision supersedes the _Decisions_, _Design_ and
_Verification_ sections below wherever they conflict. _Findings_ still stand,
and the Florida code table under _Design_ is still the content of the Focus
sheet rows.

### What changed

| Original                                         | Revised                                                                                    | From         |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------ | ------------ |
| New model `int_students__primary_sections`       | Fill the Focus columns in `int_students__course_enrollments`, plus 1 new row-number column | cbini        |
| Florida code crosswalk inline in SQL             | New columns and Focus rows on the existing course-subject crosswalk sheet                  | cbini, Gaby  |
| NJ-style labels built in SQL                     | A `Standard_Course_Name` column on that sheet                                              | cbini        |
| `course_grade_level` and a grade-match tie-break | No course grade (see _Grade_ below)                                                        | cbini, owner |
| Tie-break: latest enrollment date, then section  | Term already started, latest enrollment date, larger roster, then section                  | Gaby, cbini  |
| 1 PR                                             | 2 PRs: shared model first, DIBELS dashboard second                                         | owner        |

Settled by the owner: the data team maintains the sheet; math is included; Miami
`teacherid` is the Focus staff id.

### Grade

No SIS course grade is usable or has ever been used. Focus fills
`courses.grade_level` on 1 of 246 AY2026 courses, PowerSchool
`sections.grade_level` is not carried in the shared model, and about 20% of
Newark ELA sections read `0`. cbini's fallback, the student's enrolled grade,
would compare the enrolled grade with itself, so a grade-match step would do
nothing. The tie-break drops it. When Ops fills SIS grades, bring the grade
through and put it first in the ranking.

`schedule_student_grade_level` on the dashboard keeps `right(course_name, 1)`,
now reading `Standard_Course_Name`. It still parses a grade from a name, which
cbini's rule forbids, but the column exists to show students scheduled off-grade
(2-7 a year), and the enrolled-grade fallback would erase that.

### PR A: the sheet and the shared model

**Sheet.** The tab behind
`src_google_sheets__assessments__course_subject_crosswalk` (named range
`src_assessments__course_subject_crosswalk_v2`) gains 3 columns:

- `SIS` — `PowerSchool` or `Focus`. Every existing row is `PowerSchool`.
- `Standard_Course_Name` — the SIS-independent display name. Existing rows take
  their `PowerSchool_Course_Name`, so NJ names do not change.
- `Core_Subject` — `ELA` or `Math` when the course is a student's main class in
  that subject; blank otherwise, including Intensive Reading, Foundational ELA,
  ELA Skills and Foundation Skills Math.

Focus rows are added for the Florida codes in the table under _Design_, with
`Standard_Course_Name` set to the label in that table. Their
`Illuminate_Subject_Area`, `Is_Foundations`, `Is_Advanced_Math` and `Discipline`
stay blank, so nothing that reads those columns changes. The key becomes `SIS`
plus `PowerSchool_Course_Number`. The column keeps its name, because renaming a
Sheets header rebuilds the external table. `Duplicate_Audit` must count on the
pair. The staging uniqueness test becomes `unique_combination_of_columns` on the
pair, and both consumers — the shared model and `dim_courses` — add the `SIS`
match to their joins.

The source `columns:` and the staging contract declare the 3 new columns in the
same change. The external is re-staged in dev; the `--target staging` re-stage
needs the owner's authorization.

**Shared model.** `int_students__course_enrollments`:

- The Focus branch fills:

  | Column                  | Source                                                          |
  | ----------------------- | --------------------------------------------------------------- |
  | `courses_course_name`   | `trim(int_focus__schedule.course_title)`                        |
  | `cc_section_number`     | `int_focus__schedule.course_period_short_name`                  |
  | `cc_teacherid`          | `int_focus__schedule.teacher_id` (the Focus staff id, INT64)    |
  | `teacher_lastfirst`     | `last_name, first_name` from `int_focus__users`, already joined |
  | `rn_course_number_year` | PowerSchool's definition without `cc_termid`, which Focus lacks |

- `rn_credittype_year` and `rn_student_year_illuminate_subject_desc` stay null
  on Focus rows: Focus has no credit type, and its Illuminate subject is blank.
- Both branches carry `standard_course_name` and `core_subject` from the sheet.
- New column `rn_core_subject_year`: one section per `_dbt_source_project`,
  `cc_academic_year`, `cc_schoolid`, `students_student_number` and
  `core_subject`. It ranks only rows with a `core_subject` that are not
  `is_dropped_section`, and is null on every other row, so it avoids the defect
  cbini measured in the existing row numbers (row 1 a dropped section on 188 NJ
  student-years). Order:
  1. term already started (`cc_dateenrolled <= current_date`) first
  2. latest `cc_dateenrolled`
  3. larger roster (non-dropped rows per section and year)
  4. `cc_section_number`
- The final `full union all corresponding` stays. The PowerSchool branch is
  `a.*` over about 240 columns, and converting it to an enumerated union is its
  own change.
- Column semantics go in the properties yml, not SQL comments.

**Test.** A warn-level singular test: for the current academic year, the share
of K-8 students in `int_extracts__student_enrollments` with an
`rn_core_subject_year = 1` row, per region and subject, is at least 95%. It is
the guard Gaby asked for — a Focus or PowerSchool course missing from the sheet
shows up as a warning instead of a silent drop.

**Consumers.** 20 models filter on `rn_course_number_year = 1` or
`rn_credittype_year = 1`, and Focus rows now pass the first. The 3 Miami
dashboards among them (`rpt_tableau__miami_fast`,
`rpt_tableau__miami_k2_iready`, `rpt_tableau__miami_k2_star`) have their
refreshes off, per the owner. For the rest, NJ rows must not change, and every
Miami row a consumer gains is listed before merge.

### PR B: the DIBELS dashboard

PR B branches from PR A and is stacked on it until PR A merges; a stacked PR
runs only Trunk, so its dbt verification is local.

- Each of the 3 branches joins `int_students__course_enrollments` directly on
  `academic_year`, `_dbt_source_project`, `schoolid`, `student_number`,
  `core_subject = 'ELA'`, `rn_core_subject_year = 1` and
  `cc_section_number not like '%SC%'`.
- `course_name` comes from `standard_course_name`; the other schedule columns
  from the matching shared-model columns.
- `and not s.is_self_contained` becomes `and s.is_self_contained is not true`.
- The `teacherid` description changes to name both SIS ids.
- Docs and skill updates as in _Verification_ step 8.

### Expected effect, revised

NJ dashboard rows match prod except where the new pick differs from the old
filters, and verification lists each case:

- the 6 duplicated student-years collapse to 1 row;
- about 55 Paterson AY2023 students in `English Language Arts 5th` gain
  `ELA Gr5`, because that course shares `ENG01033G1` with `ELA Gr5`;
- students whose `rn_course_number_year = 1` row was a dropped section gain
  their live section.

Intensive Reading stays out of core ELA. 1 Miami AY2026 student (grade 6) holds
it with no main ELA course; the owner raises that student with Miami.

## Goal

Miami students appear on the Literacy Dashboard
(`rpt_tableau__dibels_dashboard`) with the same 6 schedule columns NJ carries —
`schedule_student_number`, `teacherid`, `teacher_name`, `course_name`,
`course_number`, `section_number` — plus the derived
`schedule_student_grade_level` and `scheduled`. No NJ value changes except the
removal of 6 duplicated student-years. The new model also resolves each
student's math section, so a future math consumer needs no rework.

## Findings that shape the design

Measured 2026-09-24 against prod.

1. **Miami never reaches the dashboard.** All 3 union branches filter
   `not s.is_self_contained`. That column is null on every Miami row by design —
   Focus has no source for it (#4968) — and `not null` is null, so the `WHERE`
   drops all of Miami in every year. `rpt_tableau__dibels_dashboard` holds 0
   Miami rows. Florida data has no basis for a self-contained flag, so the fix
   is a null-safe filter, not a Miami proxy.
2. **Miami AY2023-AY2025 needs no schedule work.** The frozen PowerSchool
   archive uses the NJ course names (`ELA GrK` … `ELA Gr8`) with teacher,
   section and `rn_course_number_year` populated. Student numbers already carry
   the 8400 offset and `schoolid` matches: 1,258 / 1,428 / 1,501 of 1,299 /
   1,448 / 1,514 Miami students match an ELA section.
3. **Miami AY2026+ (Focus) is the schedule gap.**
   `base_powerschool__course_enrollments` is a `select *` passthrough over
   `int_students__course_enrollments` (#3999), which already carries Focus rows.
   Its Focus branch leaves `courses_course_name`, `cc_section_number`,
   `cc_teacherid`, `teacher_lastfirst` and `rn_course_number_year` null, so the
   dashboard's join filters drop every Focus row. Focus names courses by Florida
   state course code, not by NJ course name.
4. **Today's NJ join fans out on 6 student-years.** Under the current filters, 1
   Camden AY2023 and 5 Newark AY2026 student-years match 2 ELA sections, all
   cross-grade (for example `ELA Gr7` and `ELA Gr8`, some enrolled the same
   day). Every dashboard row for those students doubles.
5. **Off-grade ELA scheduling is rare.** 2-7 students a year hold an ELA section
   whose grade differs from their enrolled grade, so preferring a grade match is
   a safe tie-break.

## Decisions

| Decision                       | Choice                                                                                    |
| ------------------------------ | ----------------------------------------------------------------------------------------- |
| Scope                          | Admit Miami (null-safe filter) and add Focus schedules                                    |
| Where the Focus logic lives    | A new SIS-neutral model, not the `int_students__course_enrollments` hub                   |
| Miami AY2026+ `course_name`    | NJ-style label (`ELA Gr3`, `Math Gr6`, `Algebra I`); real Florida code in `course_number` |
| Subjects                       | ELA and Math; only ELA has a consumer in this pass                                        |
| Miami self-contained exclusion | None — Florida data has no basis for one                                                  |
| Miami `teacherid`              | Focus `teacher_id`, the way NJ carries the PowerSchool id                                 |

The hub was rejected because `int_students__course_enrollments` sits upstream of
~184 models and 60 exposures; populating previously-null Focus columns there
changes the behavior of any consumer that filters on them, and the NJ-label
mapping would still have to live downstream. Inline-in-the-dashboard was
rejected because it keeps the 3 copied joins and cannot be reused by Bright
Spots (#4952).

## Design

### New model: `int_students__primary_sections`

`models/students/intermediate/`, materialized as a view.

**Grain:** one row per `academic_year`, `_dbt_source_project`, `schoolid`,
`student_number`, `subject` — the student's primary section in that subject at
that school that year. School stays in the key, matching the dashboard's current
join, so a mid-year transfer keeps a section per school.

**Columns:** `academic_year`, `_dbt_source_project`, `schoolid`,
`student_number`, `subject` (`ELA` / `Math`), `teacherid` (INT64),
`teacher_name` (`Last, First`), `course_name`, `course_number`,
`section_number`, `course_grade_level` (INT64, K = 0).

`course_grade_level` is explicit because `Algebra I` carries no grade in its
name; the tie-break needs it.

**Structure:**

1. **Course crosswalk CTE.** An inline list keyed on SIS and match key, yielding
   `subject`, `course_name` label and `course_grade_level`.
   - PowerSchool, matched on `trim(courses_course_name)`:
     - ELA: `ELA GrK`, `ELA K`, `ELA Gr1` … `ELA Gr8` (today's list, verbatim)
     - Math: `Math GrK` … `Math Gr8`, `Accelerated Math Gr8`, `Algebra I`,
       `Math Algebra I Honors`, `Algebra I Honors` (Miami archive). The trim is
       required: 551 NJ AY2026 grade 8 students sit in `Math Gr8 ` with a
       trailing space.
   - Focus, matched on `cc_course_number`:

     | Label                    | Grade | Florida codes                                                  |
     | ------------------------ | ----- | -------------------------------------------------------------- |
     | `ELA GrK`                | 0     | `5010041`                                                      |
     | `ELA Gr1` to `ELA Gr5`   | 1-5   | `5010042` to `5010046`, one per grade in order                 |
     | `ELA Gr6`                | 6     | `1001010`, `1001020`, `1002000`, `7810011`                     |
     | `ELA Gr7`                | 7     | `1001040`, `1001050`, `1002010`, `7810012`                     |
     | `ELA Gr8`                | 8     | `1001070`, `1001080`, `1002020`, `7810013`                     |
     | `Math GrK`               | 0     | `5012020`                                                      |
     | `Math Gr1` to `Math Gr5` | 1-5   | `5012030`, `5012040`, `5012050`, `5012060`, `5012070` in order |
     | `Math Gr6`               | 6     | `1205010`, `7812015`                                           |
     | `Math Gr7`               | 7     | `1205040`, `7812020`                                           |
     | `Math Gr8`               | 8     | `1205070`, `7812030`                                           |
     | `Algebra I`              | 8     | `1200310`, `1200320`                                           |

     Regular, advanced (ADV), ESOL and ACCESS variants share a label; the code
     in `course_number` preserves the distinction. Excluded on purpose:
     Intensive Reading (`1000010`, `1000014`) and Foundation Skills Math
     (`5012005`, `5012015`, `1204000`) — second, intervention courses nearly
     every Miami student also takes.
2. **PowerSchool rows.** `int_students__course_enrollments` joined to the
   crosswalk on the trimmed name, with today's filters:
   `rn_course_number_year = 1`, `not is_dropped_section`,
   `cc_section_number not like '%SC%'`. Columns map straight through
   (`cc_teacherid`, `teacher_lastfirst`, `cc_section_number`, …). Covers NJ in
   every year and the Miami archive.
3. **Focus rows.** `int_students__course_enrollments` Focus rows (which already
   resolve the drop flag, the offset `student_number` and `schoolid`) joined to
   the crosswalk on `cc_course_number`, to `int_focus__schedule` on
   `cc_dcid = student_schedule_id` for `course_period_short_name` (section) and
   `teacher_id`, and to `int_focus__users` for `last_name`, `first_name`. Filter
   `not is_dropped_section`.
4. **Union and pick.** Union the 2 branches (enumerated columns), join the
   student's enrolled grade at that school-year from
   `int_extracts__student_enrollments`, then `dbt_utils.deduplicate` on the
   grain, ordered by course grade equal to enrolled grade first, then latest
   `cc_dateenrolled`, then `section_number`. This resolves the 6 NJ cross-grade
   cases and the 28 Miami AY2026 students with 2 open ELA rows (16 in 2 sections
   of 1 course, 12 in 2 courses). The same-course Miami pairs pick the first
   `section_number` — arbitrary but stable, and a Focus double-scheduling for
   schools to clean up.

**Tests:** `dbt_utils.unique_combination_of_columns` on the grain (error);
`not_null` on the key columns; `accepted_values` on `subject`. The properties
yml sets `contains_pii` (the model carries `student_number`) and states that
nothing downstream exercises the math lists yet.

### Dashboard changes: `rpt_tableau__dibels_dashboard`

1. In each of the 3 branches, replace the 20-line
   `base_powerschool__course_enrollments` join with:

   ```sql
   left join
       {{ ref("int_students__primary_sections") }} as c
       on s.academic_year = c.academic_year
       and s._dbt_source_project = c._dbt_source_project
       and s.schoolid = c.schoolid
       and s.student_number = c.student_number
       and c.subject = 'ELA'
   ```

   Output column names stay the same
   (`c.student_number as schedule_student_number`, `c.teacherid`,
   `c.teacher_name`, `c.course_name`, `c.course_number`, `c.section_number`).
   `schedule_student_grade_level` (`right(c.course_name, 1)`) and `scheduled`
   keep their expressions, so NJ values do not move.

2. In each branch, `and not s.is_self_contained` becomes
   `and s.is_self_contained is not true`. NJ is never null there.
3. No column is added, dropped or renamed, so union-branch ordinals and the
   contract list are unchanged. Edit the 6 schedule column descriptions to drop
   the PowerSchool-only / null-for-Miami wording.

The dashboard stops reading `base_powerschool__course_enrollments`, removing one
#3999 consumer.

## Expected effect

- **Miami appears.** Benchmark branch estimate:

  | Year   | Rows   | Students | Scored so far |
  | ------ | ------ | -------- | ------------- |
  | AY2023 | 9,064  | 462      | 8,876         |
  | AY2024 | 20,557 | 1,431    | 17,336        |
  | AY2025 | 20,400 | 1,411    | 19,612        |
  | AY2026 | 22,044 | 1,421    | 5,951         |

  AY2023 is small because upper grades did not sit Benchmark that year. AY2026
  scores are landing (Amplify's SY2026-2027 export carries a `Kipp Florida`
  district since 2026-09-22; Miami's BOY window closes 2026-09-25). PM branches
  gain Miami AY2025 rows now and AY2026 rows once PM scores land; measured at
  build.

- **NJ is byte-identical** except the 6 fanned-out student-years, whose doubled
  rows collapse to 1.
- **Miami `scheduled`** reaches at least 97% per year for AY2023-AY2025 and
  about 98% for AY2026.

## Out of scope, visible once Miami appears

- 15 AY2025 live PM rows with a null `benchmark_goal` (Miami G0 ORF Accuracy,
  G4-5 WRF), which read as not meeting benchmark on the Aimline branch.
- Miami rounds run offset from NJ rounds, so views must filter on
  `expected_round_label`, not the bare round number.
- Whether the Benchmark branch's goal join (`s.school = g.school` against
  `stg_google_sheets__dibels_bm_goals`) matches Focus-era Miami school names.
  Checked and reported at build, not fixed here.
- The Literacy Dashboard workbook: its datasource is embedded, so views gaining
  Miami rows need a pass in Tableau Desktop.

## Verification

The dibels-dashboard skill's 8-step sequence for any field change:

1. Read back `git diff --name-only` and the SQL diff.
2. Union-branch balance on `rpt_tableau__dibels_dashboard`: same projection
   count, 0 mismatched ordinals.
3. Contract column count equals the projection count.
4. Dev build of `int_students__primary_sections` and
   `rpt_tableau__dibels_dashboard` with
   `--favor-state --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
   (absolute, because the build runs against the worktree's `--project-dir`).
5. Dev against prod, grouped by `model_type`:
   - NJ: row counts and the 6 schedule columns match prod exactly, except the 6
     known student-years (2 rows to 1).
   - Miami: rows and students per year and branch against the estimates above;
     `scheduled` rate per year.
   - Math: coverage per region; every K-8 student-year has at most 1 math row
     (AY2026 baseline 7,657 of 7,859 NJ, 1,609 of 1,632 Miami).
   - The existing dashboard tests (grain, `measure_code_sat_all_or_none`,
     `round_verdict_token_reconciles`) now run over Miami rows; a Miami failure
     is a finding to triage, not to suppress.
   - Dashboard bytes and runtime against prod. If the 3 references to the new
     view blow up the plan, materialize it as a table on the same cron tick as
     `int_students__course_enrollments`.
6. `INFORMATION_SCHEMA.COLUMNS` on the dev relations.
7. `trunk check --force --no-fix` on every changed file.
8. Update, in the same PR:
   - `docs/models/dibels-dashboard-data-model.md`
   - the dibels-dashboard skill: remove the PowerSchool-only / null-for-Miami
     schedule notes; correct the line that lists `is_self_contained` as a wrong
     cause for Miami's empty dashboard (it was wrong for AY2026 scores, but the
     filter does drop every Miami row); record the Florida code crosswalk and
     that ACCESS titles abbreviate Language Arts to `LA`, so a title search for
     `LANG` misses them.
