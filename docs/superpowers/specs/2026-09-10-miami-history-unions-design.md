# Keep 8 Miami history unions, drop 12, delete `exclude_frozen`

Design for #5193, the last open child of #5012. Brainstormed 2026-09-10. Counts
measured on `main` at `77977d0430` and in prod BigQuery the same day; re-measure
before each PR.

## Decision

kipptaf keeps Miami's PowerSchool history for two things only: stored grades and
attendance, plus the package intermediates computed from them. Every other
`source("kippmiami_powerschool", ...)` call goes. The archive dataset
`kippmiami_powerschool` becomes a permanent history source for 8 tables, and
#5012 step 4 ("remove all 33 calls") is revised to say so.

The rule behind the split is the one #5228 established: joins between
PowerSchool tables happen in the shared `powerschool` package, and kipptaf
unions only the finished, denormalized package model for blending with Focus. A
kipptaf union that exists to feed a PowerSchool-internal join is misplaced, and
one that carries Miami rows for that join is doubly so.

The archive rebuild in #5231 did not make the Miami exclusion filters redundant.
Focus Miami rows inherit `_dbt_source_project = 'kippmiami'` through every
conformed `int_students__*` model, so a filter that once kept archive rows out
of a feed now keeps Focus rows out. Of 51 literals and 12 `exclude_frozen`
calls, 0 literals and 2 calls are dead today. The rest are live business rules:
this feed does not serve Miami.

`exclude_frozen` and its var are deleted. The 7 call sites still needed after
the drops become inline `!= 'kippmiami'` literals, the form the other 42 already
use.

## The 20 remaining unions

### Keep, 8

| Chain         | Union                                   | kipptaf readers |
| ------------- | --------------------------------------- | --------------- |
| Stored grades | `stg_powerschool__storedgrades`         | 14              |
| Stored grades | `base_powerschool__final_grades`        | 11              |
| Stored grades | `int_powerschool__final_grades_rollup`  | 2               |
| Stored grades | `int_powerschool__gpa_term`             | 16              |
| Stored grades | `int_powerschool__gpa_cumulative`       | 8               |
| Attendance    | `int_powerschool__ps_adaadm_daily_ctod` | 1               |
| Attendance    | `int_powerschool__ada`                  | 1               |
| Attendance    | `int_powerschool__attendance_streak`    | 1               |

`fct_grades_term`, `fct_grades_gpa`, and `fct_grades_category` read
`int_students__final_grades`, `int_students__gpa`, and
`int_students__category_grades`, none of which touch a dropped union. The
attendance denominators are computed in the package
(`int_powerschool__ps_adaadm_daily_ctod` from `ps_membership_reg`), so no
calendar union is needed for them.

### Drop, 12

| Union                                                                                                                                  | Why                                                                                                                                                                                                                                                                             | Effect on kipptaf readers                                                                                                       |
| -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `stg_powerschool__schools`                                                                                                             | `int_students__schools` already carries Focus Miami schools under the same `school_number` values, with `name`, `abbreviation`, `school_level`, `location_key`, and project. The archive adds only the `Graduated Students` pseudo-school and lacks the 3 newest Focus schools. | 5 repoints, 6 literals and 3 calls die                                                                                          |
| `stg_powerschool__courses`                                                                                                             | Internal-join input. `storedgrades` carries `course_name` natively and `base_powerschool__final_grades` carries course attributes from the package join.                                                                                                                        | 1 literal dies; `int_students__courses` PS branch shrinks to NJ                                                                 |
| `int_powerschool__sections_union`, `int_powerschool__course_enrollments_union`                                                         | Schedule history, not on the list. The 3,433 Miami history sections leave `dim_course_sections`; their 135 course numbers exist only in the archive, so `courses` cannot drop without them.                                                                                     | 2 dead `not (kippmiami and year >= cutover)` branches in `int_students__course_sections` and `int_students__course_enrollments` |
| `stg_powerschool__assignmentscore`                                                                                                     | Gradebook, not on the list.                                                                                                                                                                                                                                                     | 2 literals die                                                                                                                  |
| `int_powerschool__teachers`, `stg_powerschool__sectionteacher`, `stg_powerschool__roledef`                                             | Section-teacher join that `base_powerschool__sections` already performs in the package.                                                                                                                                                                                         | none; readers run NJ-only                                                                                                       |
| `stg_powerschool__calendar_day`, `int_powerschool__calendar_day`, `int_powerschool__calendar_week`, `int_powerschool__calendar_rollup` | Calendar is an input to attendance, not a product of it. After PR 1 nothing in kipptaf needs Miami calendar history.                                                                                                                                                            | `dim_school_calendars` loses Miami AY2025-and-earlier days                                                                      |

The one real dependency on the calendar chain is
`int_students__attendance_daily`, which inner-joins
`int_students__calendar_week` on project to attach `week_start_monday`,
`week_end_sunday`, and `week_number_academic_year`. That join serves 793,259
Miami history rows today. PR 1 moves those 3 columns onto the package fact so
the join goes away.

## PR 1: package week fields and archive rebuild

`int_powerschool__ps_adaadm_daily_ctod` gains `week_start_monday`,
`week_end_sunday`, and `week_number_academic_year` by joining the package's own
`int_powerschool__calendar_week` on `yearid`, `schoolid`, and
`calendardate between week_start_monday and week_end_sunday`. Left join: a
membership day outside any calendar week keeps its row with null week fields,
which is what the current inner join in kipptaf silently drops and what the
verification below counts.

`kippmiami` re-includes the package with the hook YAML recorded in
`src/dbt/kippmiami/CLAUDE.md` from #5201. After merge, Charlie materializes the
`powerschool` group of `kippmiami_dbt_assets` once from prod, as in #5231. NJ
regions pick the columns up on their scheduled builds.

PR 1b removes the package from `kippmiami` again, as #5208 did. The tables stay.

## PR 2: kipptaf

One branch. Everything below compiles together because `union_relations`
intersects columns at run time and the removed relations have no kipptaf-only
columns (verified for `schools` and `courses`; check `sources-kippmiami.yml`
column lists for the other 10 before deleting).

- `int_students__attendance_daily`: read the 3 week fields from `mem`, drop the
  `int_students__calendar_week` join.
- 12 unions: delete the `source("kippmiami_powerschool", ...)` line.
- `sources-kippmiami.yml`: keep the 8 history tables. Description: "archive,
  permanent history source for stored grades and attendance; rebuilt once from
  the frozen externals with the 8400 prefix and AY2025 bound".
- 5 `schools` readers repoint to `int_students__schools`:
  `int_assessments__academic_goals`,
  `int_google_sheets__topline_aggregate_goals`,
  `int_finance__enrollment_targets`,
  `int_tableau__gradebook_audit_teacher_scaffold`, `int_kippadb__roster`.
  `rpt_deanslist__student_misc` and `rpt_gsheets__csgf_enrollment` stay on the
  union: they read principal and phone columns Focus lacks, and neither feed
  serves Miami.
- `int_students__schools`: drop its `!= 'kippmiami'` filter and the
  `powerschool_filtered` CTE.
- `exclude_frozen` macro and `frozen_powerschool_code_locations` var: delete. 7
  call sites become inline literals (5 staff-roster gates in
  `rpt_clever__staff`, `rpt_clever__teachers`, `rpt_clever__sections`;
  `sr._dbt_source_project` in `rpt_clever__students`; `sec._dbt_source_project`
  in `rpt_clever__sections`). 5 call sites are deleted (3 `schools` gates, 2 in
  `rpt_clever__enrollments`).
- `rpt_tableau__crdc_roster` lines 181 and 247: the regexp becomes
  `_dbt_source_project != 'kippmiami'`. Both filters stay live because
  `storedgrades` keeps Miami. While touched, this model and
  `rpt_clever__sections` switch from `base_powerschool__*` wrappers to the
  `int_students__*` models they alias.
- Dead literals deleted, 9: `rpt_illuminate__roles` L23, `rpt_illuminate__sites`
  L42, `int_tableau__fresh_enrollment_scaffold` L16, `rpt_parentsquare__staff`
  L10, `rpt_parentsquare__schools` L36, `int_students__schools` L22,
  `rpt_illuminate__courses` L30,
  `int_powerschool__gradebook_assignment_scores_rollup` L43,
  `rpt_deanslist__missing_assignments` L13.
- Dead branches deleted, 2: the
  `not (_dbt_source_project = 'kippmiami' and year >= fay.min_academic_year)`
  predicates in `int_students__course_sections` and
  `int_students__course_enrollments`, and the `fay` CTE if nothing else reads
  it.
- Docs: revision note on `2026-09-08-miami-powerschool-retirement-design.md` and
  a comment on #5012 rewriting steps 4 and 5.

## Filters that stay, 49

All are business rules, not archive leftovers. Recorded here so the next reader
does not re-triage them.

- 27 `region != 'Miami'` on `int_extracts__student_enrollments` and its
  descendants: NJ-only Tableau reports, Google Sheets feeds, Illuminate, DIBELS,
  graduation pathways, QBL, power standards, topline.
- 12 `_dbt_source_project != 'kippmiami'` on conformed student models that carry
  Focus Miami rows: 10 ParentSquare (Newark-only vendor),
  `rpt_illuminate__terms`, `int_extracts__gradebook_audit_student_flags`,
  `rpt_tableau__gradebook_audit`.
- 6 staff `dagster_code_location != 'kippmiami'` in Illuminate and ParentSquare,
  plus the 5 Clever staff gates inlined from the macro.
- 2 Clever inlined gates on conformed student and section models.
- 2 CRDC `storedgrades` filters. Miami files its own CRDC submission.

## Verification

PR 1: after the archive materialization, `select count(*)` of
`kippmiami_powerschool.int_powerschool__ps_adaadm_daily_ctod` equals the
pre-build count, and `countif(week_start_monday is null)` is 0 for rows whose
`calendardate` falls inside a `calendar_week` row.

PR 2, before opening:

- `uv run dbt build --select <changed>+ --defer --favor-state` from the
  worktree, per `dbt-local-dev`.
- `fct_student_attendance_daily` keeps 793,259 Miami rows at
  `academic_year <= 2025`. Fewer means the week join lost rows.
- Every kipptaf reader of the 12 dropped unions returns 0 rows at
  `_dbt_source_project = 'kippmiami'`, except readers of the 8 kept unions and
  the conformed `int_students__*` models, whose Miami counts match prod.
- The 6 `rpt_clever__*` models are row-identical to prod for
  `_dbt_source_project != 'kippmiami'`.
- The 5 repointed `schools` readers return the same NJ rows as prod and gain
  rows for the 3 Focus-only Miami schools where their sheet has targets.

## Recorded verdicts

Acceptance for #5193 is a comment listing every one of the 51 literals, 12
calls, and 20 unions against its verdict. The three sections above are that
list; the comment copies them after PR 2 merges, with final line numbers.

## Follow-up, not in scope

6 kipptaf readers still perform a PowerSchool-internal join after the drops:
`rpt_tableau__student_course_grades`, `rpt_deanslist__transcript_grades`,
`bridge_course_section_teachers`, `rpt_clever__sections`,
`int_powerschool__gradebook_assignments_scores`,
`rpt_tableau__gradebook_assignments`. They run NJ-only and produce correct
output; the join is misplaced, not wrong. One follow-up issue under #5012 moves
them into the package. The `base_powerschool__*` passthrough wrappers (57
readers) stay on #3999, widened to cover all 3.
