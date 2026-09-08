# Consolidate Miami's PowerSchool archive in the kippmiami project

Design for #5012, steps 3 to 5. Brainstormed 2026-09-08. Counts measured on
`main` at `cd6c6700d4` and in prod BigQuery the same day; re-measure before each
PR.

## Decision

Miami's PowerSchool data is frozen (final ODBC pull 2026-07-01, 90 base tables,
1.26 GiB in `kippmiami_powerschool`). The per-region calculations (`ada`, the
GPA chain, `final_grades`) are already frozen tables there. What kipptaf still
does to those rows on every build is Miami-only conformance, copied into several
models: the 8400 student-number prefix, the Focus `entrydate` re-key, and the
AY2025 cutover bound.

That conformance moves into the `kippmiami` dbt project as a
`powerschool_archive` folder of materialized tables, computed once. kipptaf's 45
PowerSchool union models then point their Miami relation at the archive (32
unions) or drop it (13 unions). No kipptaf model moves. The 3 New Jersey regions
are untouched.

Compute is not the reason. Jobs touching `kippmiami_powerschool` billed 3.3 TiB
in the last 7 days, but Miami is 8.4% of the union bytes, so the proportional
saving is about 0.28 TiB a week. The reason is that the Miami archive policy
lives in one place and kipptaf's unions stop carrying region-specific fixes.

## Archive layer (kippmiami project)

Folder `src/dbt/kippmiami/models/powerschool_archive/`, `+materialized: table`,
`+schema: powerschool_archive`, so the tables land in
`kippmiami_powerschool_archive`. Source: the frozen `kippmiami_powerschool`
dataset, declared BQ-native the way `models/fldoe/sources-bigquery.yml` already
declares it. The `focus` package is already in `packages.yml`, so
`int_focus__student_enrollment_roster` is a plain `ref()`.

One model per kipptaf union relation that keeps Miami history, same name, same
columns, plus 3 transforms:

1. Bound: `academic_year <= 2025` (or `yearid <= 35`) on every table that has
   either column. Tables without a year column (`students`, `schools`,
   `courses`, `roledef`, `sectionteacher`, `studentcorefields`,
   `u_studentsuserfields`, `gpa_cumulative`) pass through whole; they exist to
   support joins from the bounded tables.
1. Renumber: `student_number + 8400000000` on the 4 tables that carry
   `student_number` (`students`, `int_powerschool__ada`,
   `int_powerschool__attendance_streak`,
   `int_powerschool__ps_adaadm_daily_ctod`), via `focus_student_number`.
   `studentid` (the PowerSchool internal id) is untouched.
1. Re-key: on `int_powerschool__ps_adaadm_daily_ctod`, the only archive table
   that carries `entrydate`, replace it with the Focus stint's `entrydate` where
   a stint in `int_focus__student_enrollment_roster` contains `calendardate`,
   else keep the archive date. This is the PR #5158 logic, moved.

The macro `focus_student_number` moves to `src/dbt/focus/macros/utils.sql` so
every project that includes the `focus` package gets it. kipptaf keeps its own
copy: 8 vendor-file models (`stg_renlearn__star`, `int_iready__*`,
`int_amplify__mclass__*`) still renumber bare Miami ids from files, and kipptaf
does not include the `focus` package. Two copies of a one-liner, on purpose.

Archive relations (32):

- Staging (15): `assignmentscore`, `attendance`, `attendance_code`,
  `calendar_day`, `cc`, `courses`, `pgfinalgrades`, `roledef`, `schools`,
  `sectionteacher`, `storedgrades`, `studentcorefields`, `students`, `terms`,
  `u_studentsuserfields`.
- Base (1): `base_powerschool__final_grades`.
- Intermediate (16): `ada`, `attendance_streak`, `calendar_rollup`,
  `calendar_week`, `category_grades_pivot`, `course_enrollments_union`,
  `final_grades_pivot`, `gpa_cumulative`, `gpa_cumulative_year`, `gpa_term`,
  `gradescaleitem_lookup`, `ps_adaadm_daily_ctod`, `section_grade_config`,
  `sections_union`, `teachers`, `terms`.

`students`, `schools`, `studentcorefields`, and `u_studentsuserfields` are in
the archive even though the verdict policy puts students on Focus. Archive grade
and enrollment rows join them on `studentid` and `_dbt_source_project`; dropping
them would silently drop AY2025 Miami grades from every consumer that makes that
join.

Dropped relations (13), no Miami history wanted by any consumer: `users`,
`userscorefields`, `log`, `gen`, `fte`, `test`, `testscore`, `studenttest`,
`studenttestscore`, `int_powerschool__spenrollments`,
`int_powerschool__student_enrollment_union`,
`int_powerschool__district_entry_date`, `int_powerschool__teacher_grade_levels`.
Enrollment stints and district entry dates come from the Focus roster, which
#4775 made the sole Miami source.

### Dagster

The archive models are `kippmiami` dbt assets and get the eager table automation
condition. Their upstream sources have no asset events, so only the re-keyed
table rebuilds on its own, when the Focus roster updates. The other 31 rebuild
only when someone materializes them by hand after a code change. First
materialization: from the Dagster UI, `kippmiami_dbt_assets`, group
`powerschool_archive`. No cron.

## kipptaf changes

- `sources-kippmiami.yml`: add source `kippmiami_powerschool_archive` with the
  32 tables and the `dev` / `staging` (`zz_stg_`) / prod schema branch that
  every kipptaf region source needs. Prune the `kippmiami_powerschool` source to
  nothing and delete the file if no other kipptaf model reads it.
- 32 unions: swap `source("kippmiami_powerschool", X)` for
  `source("kippmiami_powerschool_archive", X)`.
- 13 unions: delete the `kippmiami` relation.
- `macros/utils.sql`: `extract_source_project` changes its regex from
  `(kipp\w+)_` to `(kipp[a-z]+)_`. Verified in BigQuery: the current pattern
  returns `kippmiami_powerschool` for a relation in
  `kippmiami_powerschool_archive`, because `\w` matches underscore. That value
  feeds every mart surrogate key hash, so it must stay `kippmiami`. The fix
  returns the same value as today for all 4 regions.
- Delete the Miami-only steps the archive now performs:
  - `focus_student_number` calls in `int_powerschool__ada`,
    `int_powerschool__attendance_streak`, and
    `int_powerschool__ps_adaadm_daily_ctod` (the archive is already prefixed; a
    second call would add 8400000000 again).
  - The `powerschool_renumbered` and re-key CTEs in
    `int_students__attendance_daily`.
  - The `focus_start_academic_year` cutover predicate in `int_students__ada`,
    `int_students__attendance_daily`, `int_students__attendance_streak`,
    `int_students__calendar_day`, `int_students__calendar_rollup`,
    `int_students__calendar_week`, `int_students__final_grades`, and
    `int_students__gpa`. The archive ends at AY2025, so the predicate is
    redundant. `int_students__sis_cutover` stays; its YAML explains the bound.
- Repoint 3 Miami-required readers of dropped or stale relations:
  `rpt_gsheets__kippfwd_miami_roster` and `rpt_gsheets__kippmiami_payout_roster`
  to `int_students__students`; `rpt_deanslist__state_test_scores` to
  `int_students__student_enrollments`, which carries `fleid` from Focus. Without
  the last one, students who joined Miami after the cutover have no FAST scores
  in DeansList.

### Verdicts for readers of a dropped relation

14 models read one of the 13 dropped relations. 7 have a Miami branch that
already reads Focus, so their Miami rows do not change:
`rpt_tableau__home_instruction`, `rpt_tableau__student_info_audit`,
`int_reporting__promotional_status`, `int_extracts__student_enrollments`,
`int_students__attendance_interventions`,
`int_students__student_enrollment_union`, `int_students__teacher_grade_levels`.
The other 7:

| Model                                                | Dropped relation           | Guard       | Verdict                                                                                                                           |
| ---------------------------------------------------- | -------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `rpt_deanslist__designations`                        | `spenrollments`            | spine, year | Focus. No change.                                                                                                                 |
| `rpt_deanslist__hs_transcript_programs`              | `spenrollments`            | none        | Focus. Miami programs are Focus data (#4802 governs content). YAML note: Miami bounded at AY2025 for PowerSchool program history. |
| `rpt_powerschool__autocomm_students`                 | `district_entry_date`      | spine, year | Focus. No change.                                                                                                                 |
| `rpt_powerschool__autocomm_teachers`                 | `users`, `userscorefields` | none        | Focus. Miami staff match no `users` row after the drop. Verify they are not emitted as new users.                                 |
| `int_powerschool__log`                               | `gen`, `log`               | none        | Focus. Miami log entries end at AY2025 and nothing reports them. YAML note.                                                       |
| `int_powerschool__state_assessments_transfer_scores` | the 4 test tables          | none        | Focus. Verify Miami rows today are 0 or unused.                                                                                   |
| `int_extracts__student_enrollments_subjects`         | `spenrollments`            | spine       | Focus. No change.                                                                                                                 |

Every other PowerSchool consumer reads only archive relations. For them PR 2 is
a pure refactor: identical Miami rows before and after. That is the acceptance
test, not a verdict.

## Filters

The 59 Miami exclusion literals and 12 `exclude_frozen` calls split by why they
exist:

1. Literals on readers of a dropped relation: delete. Dead predicate.
1. Literals and `exclude_frozen` calls on readers of an archive relation that
   also have a year predicate reaching the archive rows: delete. The archive has
   no AY2026 rows.
1. Literals and calls on current-state readers of `students`, `schools`, `cc`,
   or `sections` with no year predicate (`rpt_clever__*`, `rpt_illuminate__*`,
   `rpt_parentsquare__*`, `int_students__schools`, `int_students__students`):
   keep, converted to `exclude_frozen`. The archive `students` table still says
   `enroll_status = 0` for students who were enrolled on 2026-07-01, so a
   current-roster extract needs the gate.
1. NJ-only business rules (`rpt_gsheets__nj_state_test_roster`,
   `rpt_gsheets__njsmart_transfer_unverified`,
   `rpt_tableau__nj_school_register`, `dim_student_ell_status`, `dim_students`
   on `s_nj_stu_x`): keep as written.

`frozen_powerschool_code_locations` and `exclude_frozen` stay for group 3. The
issue's criterion that both are deleted is withdrawn (posted on #5012
2026-09-08). Group 3 is measured per consumer during PR 2, not assumed.

`rpt_tableau__crdc_roster` lines 181 and 247 become
`exclude_frozen("_dbt_source_project")`.

## Delivery

PR 1, `kippmiami`, no blockers: the 32 archive models, the `focus` macro, the
source declaration. Materialize in prod before PR 2 (two-PR pattern in
`src/dbt/CLAUDE.md`; the archive tables must exist for CI to read them).

PR 2, `kipptaf`: everything under "kipptaf changes" plus filter groups 1 and 2
and the 3 repoints. Depends on PR 1 materialized. Also touches
`int_students__ada` and `int_students__attendance_streak`, which PR #5188
(#5160) edits: either merge #5188 first and delete its renumber in PR 2, or
close #5188 as superseded because the archive renumbers those tables. Decide
before opening PR 2.

PR 3, `kipptaf`: filter group 3 conversions and `rpt_tableau__crdc_roster`.

## Verification

PR 1, per archive table, against the frozen source:

```sql
select academic_year, count(*), countif(student_number < 8400000000)
from `teamster-332318.kippmiami_powerschool_archive.<table>`
group by 1 order by 1
```

Row counts equal the frozen table filtered to AY2025 and earlier; the bare-id
count is 0 on the 4 renumbered tables. For `ps_adaadm_daily_ctod`, the 153,577
AY2025 rows PR #5158 re-dated carry the Focus `entrydate`.

PR 2, per PowerSchool consumer (145 models), before and after in dev, deferred
to prod:

```sql
select academic_year, count(*)
from `<dataset>.<model>`
where _dbt_source_project = 'kippmiami'
group by 1 order by 1
```

Identical for every reader of archive relations. 0 rows for the 7 verdict models
above. `select distinct _dbt_source_project` on every union returns the same 4
values as prod. `_dbt_source_relation` changes string for Miami rows (the
dataset name is embedded); the plan lists the consumers that expose it, starting
with `int_kippadb__roster.exit_db_name`. NJ regions row-identical to prod on
`count(*)` plus a distinct count of key columns, for every touched model.

## Blockers

None of the 5 open blockers on #5012 blocks this (#4986 and #5001 closed
2026-08-27; #4926, #4802, #4617 touch no PowerSchool union). PR #5188 is the one
sequencing dependency, for PR 2.

## Out of scope

- Dropping the `kippmiami_powerschool` dataset. It is the archive's source and
  stays.
- Moving archive grades or attendance into Focus. Focus holds no real pre-AY2026
  attendance (`int_students__sis_cutover`).
- `int_students__fldoe_fte`: `enabled: false`, nothing refs it. Florida FTE
  reporting reads `int_students__student_enrollments`, not PowerSchool.
- The 8 kipptaf vendor-file callers of `focus_student_number`.
