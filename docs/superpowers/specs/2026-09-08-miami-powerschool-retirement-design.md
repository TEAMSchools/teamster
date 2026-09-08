# Rebuild Miami's PowerSchool archive once through the powerschool package

Design for #5012, steps 3 to 5. Brainstormed 2026-09-08. Counts measured on
`main` at `cd6c6700d4` and in prod BigQuery the same day; re-measure before each
PR.

## Decision

Miami's PowerSchool data is frozen: final ODBC pull 2026-07-01, 58
`src_powerschool__*` external tables over
`gs://teamster-kippmiami/dagster/kippmiami/powerschool/` (still readable, 98,865
rows in `src_powerschool__cc`) and 90 base tables built from them in
`kippmiami_powerschool`. What kipptaf still does to those rows on every build is
Miami-only conformance, copied into several models: the 8400 student-number
prefix, the Focus `entrydate` re-key, and the AY2025 cutover bound.

The prefix and the bound get baked into the archive tables themselves. The
`kippmiami` project re-includes the shared `powerschool` package for one build,
with the ODBC staging variant enabled, `+materialized: table`, and 15 post-hooks
that renumber and bound the staging tables before any intermediate reads them.
The archive rebuilds in place into `kippmiami_powerschool`. A follow-up PR
removes the package again; the tables stay. The shared package is not edited.

kipptaf's 45 PowerSchool union models keep reading that dataset; 13 drop the
Miami relation, and the Miami-only steps in kipptaf are deleted. The re-key
stays in kipptaf because it needs the Focus roster. No new folder, dataset,
source, or package change.

Compute is not the reason. Jobs touching `kippmiami_powerschool` billed 3.3 TiB
in the last 7 days, but Miami is 8.4% of the union bytes. The reason is that the
Miami archive policy is applied once, in the archive, instead of in copied
kipptaf predicates.

## kippmiami project changes (PR 1)

- `packages.yml`: add `- local: ../powerschool` back (removed in `223c10eb60`).
- `dbt_project.yml`:

  ```yaml
  models:
    powerschool:
      +materialized: table
      sis:
        staging:
          dlt:
            +enabled: false
          odbc:
            +enabled: true
            stg_powerschool__students:
              +post-hook: >-
                update {{ this }} set student_number = student_number +
                8400000000 where true
            stg_powerschool__terms:
              +post-hook: delete from {{ this }} where yearid > 35
            # identical delete on: assignmentcategoryassoc, assignmentsection,
            # attendance, attendance_code, cc, fte, gen, gradecalculationtype,
            # gradeformulaset, gradeschoolconfig, prefs, storedgrades, termbins
  sources:
    powerschool:
      sis:
        staging:
          odbc:
            +enabled: true
  ```

  The root project may set any config on a package model, hooks included. A
  post-hook runs inside that model's build, so every dependent reads the
  renumbered, bounded rows. `stg_powerschool__students` is the only staging
  model with `student_number`, and every downstream `student_number` derives
  from it, so one `update` renumbers the archive. `yearid` 35 is AY2025. Tables
  without a year column (`students`, `schools`, `courses`, and so on) keep every
  row; they support joins from the bounded tables.

  The ODBC `sources-external.yml` resolves to
  `{{ cloud_storage_uri_base }}/powerschool/<table>/*`, the URI the frozen
  externals already use, so `stage_external_sources` recreates the same 58
  tables over the same files.

- `CLAUDE.md`: record that `kippmiami_powerschool` is rebuilt, not raw-frozen,
  and how (re-include the package with these hooks).

The `fldoe` source block for `kippmiami_powerschool` stays; after PR 1b the
package is gone again and `int_fldoe__all_assessments` keeps reading the native
source.

The hooks are warehouse `update` and `delete` statements. They run under
Dagster's dbt credentials during the one materialization, only against the 15
kippmiami tables being rebuilt in that run.

### Materialization

Branch deployments point the externals at `gs://teamster-test`, so the rebuild
runs from prod after PR 1 merges: Dagster UI, `kippmiami_dbt_assets`, group
`powerschool`, about 120 models. Their upstream `src_*` sources emit no events,
so nothing rebuilds on its own afterwards.

Building in place replaces the 2026-07-01 tables. The externals and GCS files
are the ground truth and stay; a bad build is repaired by rebuilding. Columns
may differ from the frozen copies where the package changed since July;
`union_relations` intersects columns at run time, and PR 2's compile catches a
consumer that named a dropped column.

## Remove the package again (PR 1b)

After verification passes, revert the `packages.yml` line and the
`models: powerschool:` and `sources: powerschool:` blocks. dbt does not drop a
table because its model went away, and kipptaf reads `kippmiami_powerschool` as
a BQ-native source, so nothing depends on the kippmiami manifest. kippmiami
returns to zero PowerSchool models. Keep the hook YAML in the CLAUDE.md note so
a future rebuild is a re-include.

## kipptaf changes (PR 2)

- `sources-kippmiami.yml`: remove the 13 dropped tables from the
  `kippmiami_powerschool` source. Description changes from "never rebuilt" to
  "archive, rebuilt once from the frozen externals with the 8400 prefix and
  AY2025 bound applied".
- 13 unions: delete the `kippmiami` relation. `users`, `userscorefields`, `log`,
  `gen`, `fte`, `test`, `testscore`, `studenttest`, `studenttestscore`,
  `int_powerschool__spenrollments`, `int_powerschool__student_enrollment_union`,
  `int_powerschool__district_entry_date`,
  `int_powerschool__teacher_grade_levels`. No consumer wants Miami history from
  them; enrollment stints and district entry dates come from the Focus roster,
  which #4775 made the sole Miami source.
- 32 unions: unchanged. They keep `source("kippmiami_powerschool", X)` and now
  receive bounded, renumbered rows.
- Delete the Miami-only steps the archive now carries:
  - `focus_student_number` calls in `int_powerschool__ada`,
    `int_powerschool__attendance_streak`, and
    `int_powerschool__ps_adaadm_daily_ctod`. The archive is already prefixed; a
    second call would add 8400000000 again.
  - The `powerschool_renumbered` CTE in `int_students__attendance_daily`. The
    re-key CTE that follows it stays.
  - The `focus_start_academic_year` cutover predicate in `int_students__ada`,
    `int_students__attendance_daily`, `int_students__attendance_streak`,
    `int_students__calendar_day`, `int_students__calendar_rollup`,
    `int_students__calendar_week`, `int_students__final_grades`, and
    `int_students__gpa`. The archive ends at AY2025, so it is redundant.
    `int_students__sis_cutover` stays; its YAML explains the bound.
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

| Model                                                | Dropped relation           | Guard       | Verdict                                                                                                                    |
| ---------------------------------------------------- | -------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------- |
| `rpt_deanslist__designations`                        | `spenrollments`            | spine, year | Focus. No change.                                                                                                          |
| `rpt_deanslist__hs_transcript_programs`              | `spenrollments`            | none        | Focus. Miami programs are Focus data (#4802 governs content). YAML note: Miami PowerSchool program history ends at AY2025. |
| `rpt_powerschool__autocomm_students`                 | `district_entry_date`      | spine, year | Focus. No change.                                                                                                          |
| `rpt_powerschool__autocomm_teachers`                 | `users`, `userscorefields` | none        | Focus. Miami staff match no `users` row after the drop. Verify they are not emitted as new users.                          |
| `int_powerschool__log`                               | `gen`, `log`               | none        | Focus. Miami log entries end at AY2025 and nothing reports them. YAML note.                                                |
| `int_powerschool__state_assessments_transfer_scores` | the 4 test tables          | none        | Focus. Verify Miami rows today are 0 or unused.                                                                            |
| `int_extracts__student_enrollments_subjects`         | `spenrollments`            | spine       | Focus. No change.                                                                                                          |

Every other PowerSchool consumer reads only the 32 retained relations. For them
PR 2 is a pure refactor: identical Miami rows before and after. That is the
acceptance test, not a verdict.

## Filters (PR 2 and PR 3)

The 59 Miami exclusion literals and 12 `exclude_frozen` calls split by why they
exist:

1. Literals on readers of a dropped relation: delete. Dead predicate.
1. Literals and calls on readers of a retained relation that also have a year
   predicate reaching the archive rows: delete. The archive has no AY2026 rows.
1. Literals and calls on current-state readers of `students`, `schools`, `cc`,
   or `sections` with no year predicate (`rpt_clever__*`, `rpt_illuminate__*`,
   `rpt_parentsquare__*`, `int_students__schools`, `int_students__students`):
   keep, converted to `exclude_frozen`. The archive `students` table still says
   `enroll_status = 0` for the 3,946 students who were enrolled on 2026-07-01,
   so a current-roster extract needs the gate.
1. NJ-only business rules (`rpt_gsheets__nj_state_test_roster`,
   `rpt_gsheets__njsmart_transfer_unverified`,
   `rpt_tableau__nj_school_register`, `dim_student_ell_status`, `dim_students`
   on `s_nj_stu_x`): keep as written.

`frozen_powerschool_code_locations` and `exclude_frozen` stay for group 3. The
issue's criterion that both are deleted is withdrawn (posted on #5012
2026-09-08). Group 3 membership is measured per consumer during PR 2, not
assumed.

`rpt_tableau__crdc_roster` lines 181 and 247 become
`exclude_frozen("_dbt_source_project")`.

## Delivery

1. PR 1, `kippmiami`: package include, hooks, materialization config. No
   blockers. dbt Cloud CI builds kipptaf only, so this PR's CI proves nothing
   about the build; verification happens after the prod materialization.
1. Materialize in prod from the Dagster UI. Run the PR 1 verification.
1. PR 1b, `kippmiami`: remove the include and config blocks. Fold into PR 2 only
   if the same person ships both the same day; otherwise separate, so the
   archive's provenance is one clean merge.
1. PR 2, `kipptaf`: everything under "kipptaf changes", filter groups 1 and 2,
   the 3 repoints. Depends on step 2. Also touches `int_students__ada` and
   `int_students__attendance_streak`, which PR #5188 (#5160) edits: merge #5188
   first and delete its renumber here, or close #5188 as superseded because the
   archive renumbers those tables. Decide before opening PR 2.
1. PR 3, `kipptaf`: filter group 3 conversions and `rpt_tableau__crdc_roster`.

## Verification

Before step 2, snapshot every frozen table:

```sql
select academic_year, count(*)
from `teamster-332318.kippmiami_powerschool.<table>`
group by 1 order by 1
```

After step 2: row counts equal for AY2025 and earlier; 0 rows at `yearid > 35`
in the 14 bounded tables (today `stg_powerschool__terms` carries 21 scaffold
rows there and `stg_powerschool__cc` carries 0);
`countif(student_number < 8400000000)` is 0 on `stg_powerschool__students`,
`int_powerschool__ada`, `int_powerschool__attendance_streak`, and
`int_powerschool__ps_adaadm_daily_ctod` (today all 3,946 students and 7,930 ADA
rows are bare). NJ is untouched by PR 1, so no NJ check is needed there.

PR 2, per PowerSchool consumer (145 models), before and after in dev, deferred
to prod:

```sql
select academic_year, count(*)
from `<dataset>.<model>`
where _dbt_source_project = 'kippmiami'
group by 1 order by 1
```

Identical for every reader of a retained relation. 0 rows for the 7 verdict
models. For `int_students__attendance_daily`, the 153,577 AY2025 rows PR #5158
re-dated still carry the Focus `entrydate`. NJ regions row-identical to prod on
`count(*)` plus a distinct count of key columns, for every touched model.

## Blockers

None of the 5 open blockers on #5012 blocks this (#4986 and #5001 closed
2026-08-27; #4926, #4802, #4617 touch no PowerSchool union). PR #5188 is the one
sequencing dependency, for PR 2.

## Out of scope

- Editing the shared `powerschool` package.
- Dropping the `kippmiami_powerschool` dataset or the GCS files under it. They
  are the archive's ground truth.
- Moving archive grades or attendance into Focus. Focus holds no real pre-AY2026
  attendance (`int_students__sis_cutover`).
- `int_students__fldoe_fte`: `enabled: false`, nothing refs it. Florida FTE
  reporting reads `int_students__student_enrollments`, not PowerSchool.
- The 8 kipptaf vendor-file callers of `focus_student_number`
  (`stg_renlearn__star`, `int_iready__*`, `int_amplify__mclass__*`). They
  renumber bare Miami ids from files, not from PowerSchool.
