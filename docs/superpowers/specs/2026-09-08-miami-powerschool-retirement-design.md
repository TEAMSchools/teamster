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
removes the package again; the tables stay.

The shared package gains 8 models and nothing else: every kipptaf PowerSchool
model computed exclusively on PowerSchool data moves down, so each region builds
it and kipptaf unions it like the rest. Rule: a model moves when all its inputs
are PowerSchool models the package already has. It stays when it blends another
source, reads a kipptaf snapshot, or is an extract.

kipptaf's 45 PowerSchool union models keep reading that dataset (53 after the 8
new wrappers); 13 drop the Miami relation, and the Miami-only steps in kipptaf
are deleted. After that, every kipptaf model that touches Miami PowerSchool rows
blends sources: the union wrappers, the `int_students__*` cutover models, and
the extracts. The re-key stays in kipptaf because it joins the Focus roster. No
new folder, dataset, or source.

Compute is not the reason. Jobs touching `kippmiami_powerschool` billed 3.3 TiB
in the last 7 days, but Miami is 8.4% of the union bytes. The reason is that the
Miami archive policy is applied once, in the archive, instead of in copied
kipptaf predicates.

## Package changes (PR 1)

Move 8 models from `src/dbt/kipptaf/models/powerschool/intermediate/` to
`src/dbt/powerschool/models/sis/intermediate/`, with their properties files:

| Model                                                | Lines | Reads                                                                                                                               |
| ---------------------------------------------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `int_powerschool__final_grades_rollup`               | 31    | `base_powerschool__final_grades`                                                                                                    |
| `int_powerschool__gpa_term_current`                  | 28    | `int_powerschool__gpa_term`                                                                                                         |
| `int_powerschool__gpa_term_pivot`                    | 49    | `int_powerschool__gpa_term`                                                                                                         |
| `int_powerschool__gpnode`                            | 32    | `stg_powerschool__gpnode`                                                                                                           |
| `int_powerschool__gpprogress_grades`                 | 173   | `int_powerschool__gpnode`, `base_powerschool__final_grades`, `stg_powerschool__gpprogresssubject*`, `stg_powerschool__storedgrades` |
| `int_powerschool__log`                               | 17    | `stg_powerschool__gen`, `stg_powerschool__log`                                                                                      |
| `int_powerschool__s_nj_stu_x_unpivot`                | 33    | `stg_powerschool__s_nj_stu_x`                                                                                                       |
| `int_powerschool__state_assessments_transfer_scores` | 35    | the 4 test tables                                                                                                                   |

Every input exists in the package already. Two columns the kipptaf staging
wrappers add are derived in the package copies instead: `int_powerschool__log`
inlines the fiscal-year expression for `academic_year`, and
`int_powerschool__gpprogress_grades` derives `is_transfer_grade` as `schoolname`
not matching `stg_powerschool__schools.name` (a grade earned outside the
district; kipptaf's location-crosswalk flag agrees on all but 3 rows per NJ
region). All 8 reference `_dbt_source_project` or `_dbt_source_relation`,
columns the kipptaf union adds. Inside one region project those are constant, so
the moved copy drops the `_dbt_source_*` join predicates and output columns, and
the kipptaf wrapper's `union_relations` plus `extract_source_project()` restore
them. Consumers see the same columns.

Every region that includes the package builds them (NJ as tables, per each
project's `+materialized: table` on the package). Per
`.claude/rules/dbt-models.md`, a moved model inherits the destination's config;
check the package's `sis.intermediate` block adds nothing the kipptaf copies did
not have.

Stays in kipptaf, with the reason:

- `int_powerschool__gpa_term_lookback` reads the kipptaf snapshot
  `snapshot_powerschool__gpa_term`.
- `base_powerschool__course_enrollments`, `base_powerschool__sections`,
  `base_powerschool__student_enrollments` wrap `int_students__*`, a Focus blend.
- `int_powerschool__gradebook_assignments_scores` and
  `int_powerschool__gradebook_assignment_scores_rollup` read
  `base_powerschool__course_enrollments`.
- `int_powerschool__ada_term` and `int_powerschool__ada_term_pivot` read
  `int_students__attendance_daily`.
- `int_powerschool__u_expectations_qtd_unpivot` reads
  `int_students__calendar_week`.
- `int_powerschool__gradebook_assignments`, `int_powerschool__category_grades`,
  and the NJ-only `stg_powerschool__*` wrappers are already unions.
- `rpt_*` extracts that read only PowerSchool models (`rpt_clever__schools`,
  `rpt_illuminate__courses`, and so on) are kipptaf outputs; regional projects
  wrap `kipptaf_extracts`, not the reverse.

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

The `fldoe` BigQuery-native source for `kippmiami_powerschool` is gone from
`kippmiami` (#5078 moved `int_fldoe__all_assessments` onto
`int_focus__students`), so the package model `stg_powerschool__students` owns
the Dagster asset key `[kippmiami, powerschool, stg_powerschool__students]` with
no collision.

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

Revised 2026-09-09 after PR 1 (#5201), PR 1b (#5208), and #5188 merged. The
changes from the first draft: the renumber CTE is already gone, the 4 test
tables have no kipptaf model, `state_assessments_transfer_scores` is already a
wrapper, Paterson disables the 2 grad-plan models, and PII tags are in scope.

- `sources-kippmiami.yml`: remove 13 tables from the `kippmiami_powerschool`
  source. 9 are the dropped unions below. 4 are stale entries with no kipptaf
  reader on the Miami relation: `studentrace`, `u_def_ext_students`, `period`,
  `sced_code_mapping`. Description changes from "never rebuilt" to "archive,
  rebuilt once from the frozen externals with the 8400 prefix and AY2025 bound
  applied".
- 9 unions: delete the `kippmiami` relation. `users`, `userscorefields`, `log`,
  `gen`, `fte`, `int_powerschool__spenrollments`,
  `int_powerschool__student_enrollment_union`,
  `int_powerschool__district_entry_date`,
  `int_powerschool__teacher_grade_levels`. No consumer wants Miami history from
  them; enrollment stints and district entry dates come from the Focus roster,
  which #4775 made the sole Miami source. The first draft counted 13 by
  including `test`, `testscore`, `studenttest`, and `studenttestscore`; kipptaf
  has no model for any of them and `sources-kippmiami.yml` never listed them.
- 32 unions: unchanged. They keep `source("kippmiami_powerschool", X)` and now
  receive bounded, renumbered rows.
- 7 new wrappers: the 7 models PR 1 moved into the package become
  `union_relations` wrappers over
  `source("kipp<region>_powerschool", model.name)`, the shape
  `int_powerschool__state_assessments_transfer_scores` already has. Each
  region's `sources-kipp*.yml` gains a table entry with the Dagster `asset_key`
  meta. Regions per wrapper:
  - all 4: `final_grades_rollup`, `gpa_term_pivot`
  - `gpa_term_current` is `materialized: ephemeral` in the package, so no region
    has a table to wrap. The kipptaf model stays a `where is_current` filter
    over the kipptaf `gpa_term` wrapper.
  - NJ 3: `log`, `s_nj_stu_x_unpivot`
  - Newark and Camden: `gpnode`, `gpprogress_grades` (Paterson disables both; no
    grad-plan dlt tables)

  Consumers keep their `ref()`.

- Delete the Miami-only steps the archive now carries:
  - `focus_student_number` calls in `int_powerschool__ada`,
    `int_powerschool__attendance_streak`, and
    `int_powerschool__ps_adaadm_daily_ctod`. #5188 added them; the archive is
    already prefixed and the macro's `id < 8400000000` guard makes them no-ops.
  - The `focus_start_academic_year` cutover predicate in `int_students__ada`,
    `int_students__attendance_daily`, `int_students__attendance_streak`,
    `int_students__calendar_day`, `int_students__calendar_rollup`,
    `int_students__calendar_week`, `int_students__final_grades`, and
    `int_students__gpa`. The archive ends at AY2025, so it is redundant.
    `int_students__sis_cutover` stays; its YAML explains the bound.
  - The `powerschool_renumbered` CTE in `int_students__attendance_daily` was the
    first draft's third item. #5188 removed it; nothing to do.
- Repoint 3 Miami-required readers of dropped or stale relations:
  `rpt_gsheets__kippfwd_miami_roster` and `rpt_gsheets__kippmiami_payout_roster`
  to `int_students__students`; `rpt_deanslist__state_test_scores` to
  `int_students__student_enrollments`, which carries `fleid` from Focus. Without
  the last one, students who joined Miami after the cutover have no FAST scores
  in DeansList.
- PII tags on the moved package models, column-level
  `config.meta.contains_pii: true` per `.claude/rules/ferpa-pii.md`:
  `is_iep_eligible` on `s_nj_stu_x_unpivot`; `entry` on `log`; `teacher_name`,
  `letter_grade`, and the credit columns on `gpprogress_grades`; the grade and
  GPA columns on `final_grades_rollup`, `gpa_term_pivot`, and `gpa_term_current`
  (which needs a `columns` block first). `studentid` and `studentsdcid` are
  surrogate keys and stay untagged. `gpnode` is plan structure with no student
  row and gets no tag.
- Not changed: the package's `int_powerschool__gpprogress_grades` union. Both
  branches already list every column explicitly, which is the repo's rule for a
  hand-written `union all`.

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

## Filters: deferred to #5193

The 59 Miami exclusion literals, the 12 `exclude_frozen` calls, the
`frozen_powerschool_code_locations` var, and `rpt_tableau__crdc_roster`'s regexp
filter are triaged in #5193, after the archive rebuild lands. This spec leaves
every one of them in place. Two facts from this brainstorm carry over:

- 5 of the 12 calls gate the staff roster's code location, not a PowerSchool
  table. They keep Miami staff out of Clever and are unaffected by the archive.
- The archive `students` table carries 1,114 rows at `enroll_status = 0` with
  `exitdate = 2026-06-30`, because PowerSchool was retired before the status
  rolled. A post-hook setting them to exited would make 4 of the 12 calls
  redundant. It is not needed for this spec and moves to #5193; a later fix is
  one `update` on the archive table, no rebuild.

The issue's criterion that the var and macro are deleted is withdrawn from #5012
(posted 2026-09-08) and reopened as an option on #5193.

## Delivery

1. PR 1, `powerschool` and `kippmiami`: the 8 moved models, the package include,
   hooks, materialization config. The kipptaf copies of the 8 models stay until
   PR 2, so kipptaf is untouched here. No blockers. dbt Cloud CI builds kipptaf
   only, so this PR's CI proves nothing about the build; NJ parity for the 8
   moved models is checked locally with `--target staging` against the kipptaf
   copies before merge.
1. Materialize in prod. NJ regions pick up the 8 new models on their next
   upstream update (eager table condition). Miami: Dagster UI,
   `kippmiami_dbt_assets`, group `powerschool`. Run the PR 1 verification.
1. PR 1b, `kippmiami`: remove the include and config blocks. Fold into PR 2 only
   if the same person ships both the same day; otherwise separate, so the
   archive's provenance is one clean merge.
1. PR 2, `kipptaf`: everything under "kipptaf changes" and the 3 repoints.
   Depends on step 2 for all 4 regions (done 2026-09-09). #5188 (#5160) merged
   2026-09-08, so PR 2 deletes its 3 `focus_student_number` calls.
1. #5193 picks up the filters.

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
rows are bare). For the 8 moved models, each NJ region's package output is
row-identical to the kipptaf copy filtered to that region, on `count(*)` plus a
distinct count of the key columns.

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

- Every Miami exclusion filter, `exclude_frozen`, its var, and the
  `enroll_status` hook: #5193.
- Dropping the `kippmiami_powerschool` dataset or the GCS files under it. They
  are the archive's ground truth.
- Moving archive grades or attendance into Focus. Focus holds no real pre-AY2026
  attendance (`int_students__sis_cutover`).
- `int_students__fldoe_fte`: `enabled: false`, nothing refs it. Florida FTE
  reporting reads `int_students__student_enrollments`, not PowerSchool.
- The 8 kipptaf vendor-file callers of `focus_student_number`
  (`stg_renlearn__star`, `int_iready__*`, `int_amplify__mclass__*`). They
  renumber bare Miami ids from files, not from PowerSchool.
