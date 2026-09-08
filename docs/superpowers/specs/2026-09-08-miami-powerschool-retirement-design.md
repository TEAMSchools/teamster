# Retire Miami from the Focus-only PowerSchool unions

Design for #5012, steps 3 to 5. Brainstormed 2026-09-08. Counts measured on
`main` at `cd6c6700d4`; re-measure with the scripts in the issue fold-out before
each PR.

## Decision

Miami's PowerSchool archive stays the source for Miami course enrollments,
grades, attendance, and calendar through AY2025. It stops being a source for
everything else. So this is a partial retirement: 11 unions drop `kippmiami`, 22
keep it and become the documented archive.

The verdict policy (issue comment of 2026-09-08) decides which is which:

| Policy row                             | Miami source                              | Union set |
| -------------------------------------- | ----------------------------------------- | --------- |
| Course enrollments, stored grades, GPA | Archive through AY2025, Focus from AY2026 | keep      |
| Attendance, ADA, streak, calendar      | Same split                                | keep      |
| Everything else                        | Focus only                                | drop      |

Terms, courses, grade-scale lookups, and the teacher tables sit in the first row
even though the policy text does not name them.
`rpt_deanslist__transcript_grades`, `rpt_tableau__student_course_grades`, and
`int_students__courses` join archive grades to `terms` and `courses`;
`bridge_course_section_teachers` joins archive sections to `sectionteacher`,
`roledef`, and `int_powerschool__teachers`. Dropping Miami from those would
orphan AY2025 grade rows.

## Union sets

Drop `kippmiami` (11):

- `stg_powerschool__students`
- `stg_powerschool__users`
- `stg_powerschool__schools`
- `int_powerschool__spenrollments`
- `stg_powerschool__log`
- `stg_powerschool__gen`
- `stg_powerschool__test`
- `stg_powerschool__testscore`
- `stg_powerschool__studenttest`
- `stg_powerschool__studenttestscore`
- `stg_powerschool__fte`

Keep `kippmiami` (22): `stg_powerschool__cc`, `int_powerschool__sections_union`,
`stg_powerschool__sectionteacher`, `stg_powerschool__roledef`,
`int_powerschool__teachers`, `stg_powerschool__courses`,
`stg_powerschool__terms`, `int_powerschool__terms`,
`stg_powerschool__storedgrades`, `stg_powerschool__pgfinalgrades`,
`stg_powerschool__assignmentscore`, `base_powerschool__final_grades`,
`int_powerschool__final_grades_pivot`, `int_powerschool__gpa_term`,
`int_powerschool__gpa_cumulative`, `int_powerschool__gpa_cumulative_year`,
`int_powerschool__gradescaleitem_lookup`,
`int_powerschool__section_grade_config`, `stg_powerschool__attendance`,
`int_powerschool__ada`, `stg_powerschool__calendar_day`,
`int_powerschool__calendar_week`.

`sources-kippmiami.yml` (90 tables) is pruned to the 22 kept tables plus their
package-side inputs, not deleted.

## Verdicts

A consumer that reads only kept unions cannot change rows in this work. Its
verdict is "archive, unchanged" by construction and it is not listed. Of the 87
consumers with no Miami literal, 59 are in that group.

The 27 that read a dropped union and are not Miami-required, plus the 3
Miami-required models whose Miami branch does not touch the dropped union, with
the guard that already narrows them:

| Model                                                | Dropped union read                             | Guard        | Verdict                                                                                                                                                                                                                                                               |
| ---------------------------------------------------- | ---------------------------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rpt_branchingminds__course_performance`             | students                                       | year         | Focus. No change needed.                                                                                                                                                                                                                                              |
| `rpt_clever__enrollments`                            | students                                       | year         | Focus. Delete its `exclude_frozen` call.                                                                                                                                                                                                                              |
| `rpt_clever__sections`                               | schools                                        | year         | Focus. Delete its `exclude_frozen` call.                                                                                                                                                                                                                              |
| `rpt_deanslist__designations`                        | spenrollments                                  | spine, year  | Focus. No change.                                                                                                                                                                                                                                                     |
| `rpt_deanslist__student_misc`                        | schools                                        | spine, year  | Focus. No change.                                                                                                                                                                                                                                                     |
| `rpt_deanslist__transcript_gpas`                     | students                                       | spine        | Focus. No change.                                                                                                                                                                                                                                                     |
| `rpt_gsheets__csgf_enrollment`                       | schools                                        | spine, year  | Focus. No change.                                                                                                                                                                                                                                                     |
| `rpt_littlesis__enrollments`                         | schools                                        | year         | Focus. No change.                                                                                                                                                                                                                                                     |
| `rpt_powerschool__autocomm_students`                 | students                                       | spine, year  | Focus. No change.                                                                                                                                                                                                                                                     |
| `rpt_tableau__student_attrition_over_time_v1`        | students                                       | spine, year  | Focus. No change.                                                                                                                                                                                                                                                     |
| `int_kippadb__roster`                                | schools                                        | spine, year  | Focus. No change.                                                                                                                                                                                                                                                     |
| `int_extracts__course_schedule_by_term`              | schools                                        | year         | Focus. No change.                                                                                                                                                                                                                                                     |
| `int_extracts__student_enrollments_subjects`         | spenrollments                                  | spine        | Focus. No change.                                                                                                                                                                                                                                                     |
| `int_assessments__academic_goals`                    | schools                                        | none         | Focus. Reads school names; Miami names come from `int_students__schools`. Verify by row count.                                                                                                                                                                        |
| `rpt_clever__schools`                                | schools                                        | none         | Focus. Delete its `exclude_frozen` call.                                                                                                                                                                                                                              |
| `rpt_clever__staff`                                  | schools                                        | none         | Focus. Delete its `exclude_frozen` call.                                                                                                                                                                                                                              |
| `rpt_deanslist__family_contacts`                     | students                                       | none         | Focus. Miami contacts come from Finalsite (#5110 may retire the feed).                                                                                                                                                                                                |
| `rpt_deanslist__hs_transcript_programs`              | students, spenrollments                        | none         | Focus. Miami programs come from Focus (#4802 governs content).                                                                                                                                                                                                        |
| `rpt_deanslist__transcript_grades`                   | students, schools                              | none         | Archive for grades, Focus for the student join. Verify AY2025 Miami rows survive; if they drop, the student join must move to the spine.                                                                                                                              |
| `rpt_powerschool__autocomm_teachers`                 | users                                          | none         | Focus. Joins the staff roster to `users` on code location, so Miami staff already match nothing after the drop. Verify Miami staff rows are not emitted as new users; if they are, gate the roster with `exclude_frozen("home_work_location_dagster_code_location")`. |
| `rpt_tableau__college_assessment_dashboard_de`       | students                                       | none         | Focus. Verify by row count.                                                                                                                                                                                                                                           |
| `int_finance__enrollment_targets`                    | schools                                        | none         | Focus. School lookup only.                                                                                                                                                                                                                                            |
| `int_google_sheets__dibels_pm_expectations`          | schools                                        | none         | Focus. School lookup only.                                                                                                                                                                                                                                            |
| `int_google_sheets__topline_aggregate_goals`         | schools                                        | none         | Focus. School lookup only.                                                                                                                                                                                                                                            |
| `int_powerschool__gradebook_assignments_scores`      | schools                                        | none         | Archive for scores (reads `assignmentscore`), Focus for the school join. Verify AY2025 Miami rows survive.                                                                                                                                                            |
| `int_powerschool__log`                               | gen, log                                       | none         | Focus. Miami log entries end at AY2025 and nothing reports them. Bound at AY2025 in the YAML description.                                                                                                                                                             |
| `int_reporting__promotional_status`                  | gen, log                                       | Miami branch | Focus. The Miami thresholds read grades and attendance only; `gen` and `log` feed the NJ branch. No change.                                                                                                                                                           |
| `rpt_tableau__home_instruction`                      | spenrollments                                  | none         | Focus. Miami home-instruction rows vanish until Focus program enrollments are modeled (#4802 governs the source data). Bound at AY2025 in the YAML description.                                                                                                       |
| `rpt_tableau__student_info_audit`                    | fte                                            | year         | Focus. Scoped to `current_academic_year`, so Miami archive rows never reach the `fte` join. No change.                                                                                                                                                                |
| `int_powerschool__state_assessments_transfer_scores` | test, testscore, studenttest, studenttestscore | none         | Focus. Miami transfer scores were never loaded to PowerSchool. Verify by row count.                                                                                                                                                                                   |

Guards: "spine" means a join to `int_students__student_enrollments`,
`int_extracts__student_enrollments`, `int_students__students`, or the enrollment
union, where Miami archive rows never match. "year" means a
`current_academic_year` predicate; the archive ends at AY2025. Static grep, so
the "Verify" rows get a before-and-after Miami row count in PR 2.

Only models whose rows change get a YAML note. The rest carry the verdict here.

## Miami-required consumers of a dropped union

These read Miami rows from a dropped union on purpose. Each is repointed in PR
1, before the union changes.

| Model                                  | Dropped union read               | Repoint to                                                                                                                                                                                                  |
| -------------------------------------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rpt_gsheets__kippfwd_miami_roster`    | students                         | `int_students__students`                                                                                                                                                                                    |
| `rpt_gsheets__kippmiami_payout_roster` | students                         | `int_students__students`                                                                                                                                                                                    |
| `rpt_deanslist__state_test_scores`     | students, `u_studentsuserfields` | `int_students__student_enrollments`, which carries `fleid` from Focus. The FAST join is Miami's only state-test path in this feed, so without the repoint every Miami FAST score disappears from DeansList. |

`int_students__fldoe_fte` is `enabled: false` and nothing refs it. Florida FTE
reporting reads `is_fldoe_fte_2` and `is_fldoe_fte_3` from
`int_students__student_enrollments`, sourced from
`stg_google_sheets__reporting__terms`. The issue's acceptance criterion about
Florida state reporting is satisfied by the archive grade and attendance unions
staying in place; no model in this spec produces those numbers.

## Filters

The 59 Miami exclusion sites in 43 models split 3 ways:

1. Sites whose column comes from a dropped union: delete. The union no longer
   carries Miami, so the predicate is dead. Of the 12 `exclude_frozen` calls, 4
   are in this group: `rpt_clever__schools` line 25, `rpt_clever__staff` line
   59, `rpt_clever__sections` line 39, and `rpt_clever__enrollments` line 32,
   all on `stg_powerschool__schools` or `stg_powerschool__students`.
1. Sites whose column comes from a kept union (`cc`, `course_enrollments`,
   `storedgrades`, `final_grades`, `sections`) or from the staff roster's code
   location: convert each literal to `exclude_frozen(column)`. The policy then
   lives in one macro. The other 8 `exclude_frozen` calls are already in this
   shape and stay, including `rpt_clever__enrollments` line 17 on `cc`.
1. NJ-only business rules (`rpt_gsheets__nj_state_test_roster`,
   `rpt_gsheets__njsmart_transfer_unverified`,
   `rpt_tableau__nj_school_register`, `dim_student_ell_status`, `dim_students`
   on `s_nj_stu_x`): keep as written. These exclude Miami because the report is
   about New Jersey, not because of the archive.

The `frozen_powerschool_code_locations` var and `exclude_frozen` macro stay. The
macro comment changes from "frozen" to "archive" wording. The issue's acceptance
criterion that both are deleted is withdrawn: with 22 unions still carrying
Miami, current-state consumers of those unions need the gate.

`rpt_tableau__crdc_roster` lines 181 and 247 filter Miami with a regexp on
`_dbt_source_relation` inside `WHERE`. Convert to
`exclude_frozen("_dbt_source_project")` in the same pass.

## Delivery

Three PRs. Each is green and revertible alone.

PR 1, no blockers: repoint the 3 Miami-required consumers above. Post the
verdict table to #5012.

PR 2, no blockers: drop `kippmiami` from the 11 unions, prune
`sources-kippmiami.yml`, delete the group-1 filters, add the YAML notes to
`int_powerschool__log` and `rpt_tableau__home_instruction`.

PR 3, after PR #5188 (#5160) merges: convert group-2 literals to
`exclude_frozen`, fix `rpt_tableau__crdc_roster`, reword the macro comment. PR
#5188 edits `int_students__ada` and `int_students__attendance_streak`, both
group-2 files.

## Verification

Before PR 2, per model in the "Verify" rows and the 5 repointed models:

```sql
select academic_year, count(*)
from `teamster-332318.<dataset>.<model>`
where _dbt_source_project = 'kippmiami'
group by 1 order by 1
```

Saved to `.claude/scratch/` in the PR branch and quoted as aggregates in the PR
body. After PR 2 builds in dev (`uv run dbt build --select <union>+` per dropped
union, deferred to prod per `dbt-local-dev`), the same query must return
identical rows for archive consumers and 0 rows for Focus-only consumers. Any
other result is a wrong verdict, and the PR does not merge until the table above
is corrected.

NJ parity on every PR: the 3 NJ regions row-identical to prod on `count(*)` plus
a distinct count of the key columns, for every touched model.

## Blockers

Of the 5 open blockers on #5012, none blocks this work:

- #4986 and #5001 closed 2026-08-27.
- #4926 (KIPP Foundation feeds) reads Focus-backed models and
  `int_powerschool__ada`, a kept union.
- #4802 and #4617 are Focus and Finalsite data-entry gaps; no PowerSchool union
  feeds the fields they cover.

The one live dependency is PR #5188, for PR 3 only.

## Out of scope

- Deleting `sources-kippmiami.yml` or the `kippmiami` code location's
  PowerSchool models. The archive stays materialized.
- Moving archive grades or attendance into Focus. Focus holds no real pre-AY2026
  attendance (`int_students__sis_cutover`).
- The `exclude_frozen` calls on staff-roster code-location columns in
  `rpt_clever__staff`, `rpt_clever__teachers`, `rpt_clever__sections`, and
  `rpt_clever__students`. They keep Miami staff and students out of Clever
  because Clever serves the PowerSchool regions, and no union change affects
  them.
