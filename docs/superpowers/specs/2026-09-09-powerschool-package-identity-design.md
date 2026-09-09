# PowerSchool package identity: drop Miami from students and 14 more unions

Issue: #5228. Parent: #5012. Parent design:
`2026-09-08-miami-powerschool-retirement-design.md`.

## Decision

The shared `powerschool` package resolves student identity and school attributes
on every fact that kipptaf reads for Miami history. kipptaf stops joining
`stg_powerschool__students`, `stg_powerschool__schools`, and
`stg_powerschool__terms` onto PowerSchool facts. Then the students union and 14
more unions drop the `kippmiami` relation.

The pattern already exists. `base_powerschool__course_enrollments` joins
students and sections inside the package and emits `students_student_number`,
`school_name`, `school_abbreviation`, and `school_level` next to `cc_studentid`.
Miami's attendance, course enrollment, category grade, and gradebook history
already reaches kipptaf through that column. This change extends the same shape
to GPA, final grades, calendar days, and entry school, and rebuilds the Miami
archive once so the new columns exist for Miami.

Why the archive students table cannot go without this: every archive fact keys
students by `studentid`, the PowerSchool surrogate. `stg_powerschool__students`
is the only staging model with `student_number`. Focus carries `powerschool_id`,
the old bare number, but never `studentid`, so Focus cannot bridge an archive
grade row to a student. Ops will not import stored grades or course enrollments
into Focus, so the archive is permanent and kipptaf keeps reading it.

Miami Focus enrollments carry `studentid = null`
(`int_students__student_enrollments`), so the 30-odd grade and GPA readers that
resolve students through `int_extracts__student_enrollments.studentid` already
see no Miami archive rows. Only the 20 direct readers of
`stg_powerschool__students` can reach Miami history, and 3 of them do it on
purpose: `int_students__gpa`, `int_students__final_grades`, and
`rpt_gsheets__kippfwd_miami_roster`.

Considered and declined:

- A kipptaf-only identity bridge (a 4-region union of `studentid`,
  `students_dcid`, `student_number`). No rebuild, but it is the Miami slice of
  `stg_powerschool__students` under another name, and it leaves NJ readers
  joining students too.
- A package `int_powerschool__storedgrades` with identity columns. No kipptaf
  reader needs a Miami `student_number` on raw stored grades: the DeansList
  transcript models and Branching Minds are NJ only, and the dual-enrollment
  dashboard has no Miami rows (verified in Verification). Write it the day a
  reader needs it.
- Dropping Miami from `stg_powerschool__schools`. 3 Google Sheets readers
  (`int_assessments__academic_goals`,
  `int_google_sheets__topline_aggregate_goals`,
  `int_finance__enrollment_targets`) join it to attach Miami school attributes
  to sheet rows keyed by school number. Repointing them to the blended
  `int_students__schools` needs a check that the sheets use ids Focus
  recognizes. That is #5193 option 2.

## Package changes (PR A)

All in `src/dbt/powerschool/models/sis`. Identity columns follow the
`base_powerschool__course_enrollments` names: `students_dcid`,
`students_student_number`. School columns follow `base_powerschool__sections`:
`school_name`, `school_abbreviation`, `school_level`. No other student or school
columns; the readers only need the key and a label.

| Model                                                                                                  | Change                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `base_powerschool__final_grades`                                                                       | Pass `students_dcid`, `students_student_number`, `school_abbreviation`, `school_level` through from course enrollments. It reads them today and drops them; `school_name` is already there.                                                                                                                                                                             |
| `int_powerschool__gpa_term`, `int_powerschool__gpa_cumulative`, `int_powerschool__gpa_cumulative_year` | Join `stg_powerschool__students` on `studentid = id` and `stg_powerschool__schools` on `schoolid = school_number`. Emit `students_student_number` and the 3 school columns. `gpa_term_pivot` and `gpa_term_current` list their columns explicitly and are unchanged; no kipptaf reader needs identity on them.                                                          |
| `int_powerschool__calendar_day` (new)                                                                  | `stg_powerschool__calendar_day` left joined to `stg_powerschool__terms` on `schoolid` and `date_value between firstday and lastday` where `isyearrec = 1`, and to schools. Emits `yearid`, `academic_year`, the 3 school columns, and `schoolcity`. Left join, so a day with no covering term keeps flowing with null year, as `int_students__calendar_day` does today. |
| `base_powerschool__student_enrollments`                                                                | Add `entry_school_abbreviation` by joining schools on `entry_schoolid`.                                                                                                                                                                                                                                                                                                 |

Not changed: `stg_powerschool__students`, `cc`, `storedgrades`, the dcid-keyed
extension tables (`u_studentsuserfields`, `studentcorefields`, `s_stu_x`),
`category_grades`, `gpprogress_grades`. Their kipptaf readers are NJ-only or
current-state, and an NJ-only students union is the right join for them.

PII: `students_student_number` and its `config.meta.contains_pii: true` tag are
added to all 4 models — the 3 GPA models and `base_powerschool__final_grades` —
in the package YAML, per `.claude/rules/ferpa-pii.md`.

Also in PR A: `src/dbt/kippmiami` re-includes the package with the ODBC staging
variant, `+materialized: table`, and the 16 post-hooks (15 from #5201 plus the
`calendar_day` bound recorded in `src/dbt/kippmiami/CLAUDE.md` by #5224). This
is the #5195 diff replayed; the hook YAML is unchanged.

## Miami archive rebuild

One prod Dagster build of the kippmiami PowerSchool assets, run by the user,
same as PR 1. `students` builds first because the GPA models depend on it, so
its renumber hook finishes before any dependent reads it. The new
`int_powerschool__calendar_day` lands as a table. Every other archive table
rebuilds to the rows it has now.

The rebuild has to prove two things before PR B opens; see Verification.

## kipptaf changes (PR B)

PR B also reverts the kippmiami package include, the #5196 diff replayed, and
runs `dbt deps` for kippmiami so the stale local package is pruned.

Wrappers: the existing union wrappers for `gpa_term`, `gpa_cumulative`,
`gpa_cumulative_year`, `base_powerschool__final_grades`, and
`base_powerschool__student_enrollments` pick up the new columns on their own,
because `dbt_utils.union_relations` reads each relation's columns at compile
time. One new wrapper, `int_powerschool__calendar_day`, in the shape #5224 used
for the moved models, with a table entry in each of the 4 `sources-kipp*.yml`.
It re-declares `contains_pii` at model level if any source column carries it.

Readers that drop a PowerSchool join:

| Model                                                                                                                                                              | Edit                                                                                                                         |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| `int_students__gpa`, `int_students__final_grades`                                                                                                                  | Delete the `ps_students` CTE. Read `students_student_number` from the fact. The `focus_start_academic_year` predicate stays. |
| `rpt_gsheets__kippfwd_miami_roster`                                                                                                                                | Delete `ps_xwalk`. Join `gpa_cumulative` and `gpa_term` on `students_student_number = s.student_id`.                         |
| `rpt_gsheets__kippmiami_payout_roster`                                                                                                                             | Repoint students to `int_students__students`. The model is `enabled: false`; the edit keeps it compilable.                   |
| `int_students__calendar_day`                                                                                                                                       | Read the new wrapper. Delete the terms join.                                                                                 |
| `int_google_sheets__dibels_pm_expectations`                                                                                                                        | Read `schoolcity` from the new wrapper. Delete the schools join.                                                             |
| `int_kippadb__roster`                                                                                                                                              | Read `entry_school_abbreviation`. Delete the schools join.                                                                   |
| `int_extracts__course_schedule_by_term`, `int_powerschool__gradebook_assignments_scores`, `rpt_littlesis__enrollments`, `rpt_tableau__state_assessments_dashboard` | Read `school_level`, `school_level`, `school_name`, `school_abbreviation` from the fact. Delete the schools join.            |

The last row needs no package change: `base_powerschool__course_enrollments`
stars every `base_powerschool__sections` column, so those 4 joins are redundant
today.

Unions that drop the `kippmiami` relation, and lose the matching table in
`sources-kippmiami.yml`:

| Union                                                                                                                                                                                                        | Why no reader keeps Miami rows                                                                                |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| `stg_powerschool__students`                                                                                                                                                                                  | The 3 history readers now take identity from the fact. Every other reader excludes Miami or is current-state. |
| `stg_powerschool__attendance`, `stg_powerschool__attendance_code`                                                                                                                                            | No kipptaf readers.                                                                                           |
| `stg_powerschool__studentcorefields`, `stg_powerschool__u_studentsuserfields`, `stg_powerschool__terms`, `int_powerschool__terms`, `int_powerschool__gpa_cumulative_year`, `int_powerschool__gpa_term_pivot` | Every reader excludes Miami by literal.                                                                       |
| `stg_powerschool__pgfinalgrades`, `int_powerschool__category_grades_pivot`, `int_powerschool__final_grades_pivot`, `int_powerschool__section_grade_config`                                                   | Every reader filters to `current_academic_year`; the archive ends at AY2025.                                  |
| `stg_powerschool__cc`, `int_powerschool__gradescaleitem_lookup`                                                                                                                                              | Readers exclude by `exclude_frozen` or by an inner join through students.                                     |

These verdicts came from a reader-by-reader read of the SQL. Each one is
re-verified with row counts in the plan before the relation is removed, because
a wrong drop returns fewer rows and nothing errors.

The 18 unions that keep Miami are the history facts Miami reporting reads on
purpose: `assignmentscore`, `calendar_day`, `courses`, `roledef`,
`sectionteacher`, `storedgrades`, `base_powerschool__final_grades`, `ada`,
`attendance_streak`, `calendar_rollup`, `calendar_week`, `category_grades`,
`course_enrollments_union`, `final_grades_rollup`, `gpa_cumulative`, `gpa_term`,
`ps_adaadm_daily_ctod`, `sections_union`, `teachers`. Plus `schools`, per
Decision.

Dead literals deleted in PR B, because the students union can no longer return
Miami: `int_students__students`, `int_students__student_core_fields`,
`int_students__student_user_fields`, `int_tableau__fresh_enrollment_scaffold` (2
sites), `stg_people__student_logins`. Every other Miami literal and all 12
`exclude_frozen` calls stay for #5193.

## Delivery

1. PR A: package models, package PII YAML, kippmiami package include. NJ regions
   rebuild the changed models on merge. Miami builds nothing until step 2.
2. Prod run: the user materializes the Miami archive. Claude runs the archive
   checks below.
3. PR B: kippmiami package removal, kipptaf wrapper, reader edits, union drops,
   dead literals, wrapper PII tags.

PR B cannot land before step 2. `union_relations` fills a column one relation
lacks with null, so `int_students__gpa` would read null
`students_student_number` for Miami and lose its archive branch in between.

## Verification

Counts only. No student-level rows leave the terminal.

| Check              | Passes when                                                                                                                                                                                                                      |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Package, NJ        | `count(*)` and `count(distinct <key>)` on each changed model equal prod per region. The new identity and school columns are non-null on every row of the GPA and final grades models.                                            |
| Miami archive      | Every `students_student_number` on the 3 GPA tables is at or above 8400000000. Every untouched table matches its #5224 verification row count. `int_powerschool__calendar_day` row count equals `stg_powerschool__calendar_day`. |
| Kipptaf readers    | Every touched model is row-identical to prod per `_dbt_source_project` per `academic_year`, Miami included where it keeps Miami.                                                                                                 |
| The 15 union drops | Every direct kipptaf reader of each dropped union has the same total row count before and after. Any difference means the verdict was wrong; restore the relation and record why.                                                |
| Students union     | `stg_powerschool__students` returns 0 rows where `_dbt_source_project = 'kippmiami'`.                                                                                                                                            |
| Assumption         | `rpt_tableau__college_assessment_dashboard_de` has 0 Miami rows on prod today. If not, the stored grades identity model comes back into scope.                                                                                   |
| Column gate        | `dbt build --empty --select state:modified+ --target dev --defer --favor-state` against the refreshed prod manifest passes for every touched file.                                                                               |

## Effect on #5193

The exit-marking DML is no longer needed: `rpt_clever__enrollments` cannot see
Miami students or Miami `cc` rows. Its 2 `exclude_frozen` calls and the one on
`rpt_clever__students` become dead. #5193 shrinks to the 3 `schools` calls, the
5 staff-roster gates, the schools question, and whatever literals survive the
triage.

## Out of scope

- The 59 Miami literals outside the 6 named above, `exclude_frozen`, and
  `frozen_powerschool_code_locations` (#5193).
- `stg_powerschool__schools` dropping Miami (#5193 option 2).
- Package school or term columns on facts no kipptaf reader joins a dimension
  onto today.
- Dropping `kippmiami_powerschool` or its GCS files.
