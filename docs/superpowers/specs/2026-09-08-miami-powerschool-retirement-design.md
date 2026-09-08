# Rebuild Miami's PowerSchool archive through the shared powerschool package

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

The prefix and the bound move into the shared `powerschool` package as 2
var-driven transforms that render as no-ops for New Jersey. The `kippmiami`
project re-includes the package with the ODBC staging variant enabled and
`+materialized: table`, and rebuilds the archive once, in place, into
`kippmiami_powerschool`. kipptaf's 45 PowerSchool union models keep reading that
dataset; 13 of them drop the Miami relation, and the Miami-only steps in kipptaf
are deleted. The re-key stays in kipptaf because it needs the Focus roster,
which the package cannot ref. No new folder, no new dataset, no new source
declaration.

Compute is not the reason. Jobs touching `kippmiami_powerschool` billed 3.3 TiB
in the last 7 days, but Miami is 8.4% of the union bytes. The reason is that the
Miami archive policy lives in the package, once, instead of in copied kipptaf
predicates.

## Package changes (`src/dbt/powerschool`)

Both transforms live in the staging layer, because every downstream column
derives from there. Apply them in the `odbc` and `dlt` variants, so the siblings
stay in step per `src/dbt/powerschool/CLAUDE.md`. Defaults keep New Jersey
output byte-identical.

1. Renumber. `stg_powerschool__students` is the only staging model that carries
   `student_number`; every `student_number` in `int_*` and `base_*` comes from a
   join to it. Where it casts the column:

   ```sql
   cast(student_number.double_value as int)
   + {{ var("powerschool_student_number_offset", 0) }} as student_number,
   ```

   Not `focus_student_number`: that macro is conditional on year, and the
   archive is bounded to AY2025 by transform 2, so the offset applies to every
   row.

1. Bound. New `macros/archive.sql` (the package already declares
   `macro-paths: [macros]`):

   ```sql
   {% macro powerschool_archive_bound(yearid) -%}
       {%- set max_yearid = var("powerschool_archive_max_yearid", none) -%}
       {%- if max_yearid is none %}true{% else %}{{ yearid }} <= {{ max_yearid }}{% endif -%}
   {%- endmacro %}
   ```

   Added as a `where` predicate to the 14 ODBC staging models with `yearid`
   (`assignmentcategoryassoc`, `assignmentsection`, `attendance`,
   `attendance_code`, `cc`, `fte`, `gen`, `gradecalculationtype`,
   `gradeformulaset`, `gradeschoolconfig`, `prefs`, `storedgrades`, `termbins`,
   `terms`) and their 13 dlt siblings. Tables without a year column (`students`,
   `schools`, `courses`, and so on) pass through whole; they support joins from
   the bounded tables.

`kippmiami` sets `powerschool_student_number_offset: 8400000000` and
`powerschool_archive_max_yearid: 35` (AY2025). NJ projects set neither.

## kippmiami project changes

- `packages.yml`: add `- local: ../powerschool` back (removed in `223c10eb60`).
- `dbt_project.yml`:

  ```yaml
  powerschool:
    +materialized: table
    sis:
      staging:
        dlt:
          +enabled: false
        odbc:
          +enabled: true
  sources:
    powerschool:
      sis:
        staging:
          odbc:
            +enabled: true
  ```

  plus the 2 vars above. The ODBC `sources-external.yml` resolves to
  `{{ cloud_storage_uri_base }}/powerschool/<table>/*`, which is the URI the
  frozen externals already use, so `stage_external_sources` recreates the same
  58 tables over the same files.

- `models/fldoe/sources-bigquery.yml`: delete the `kippmiami_powerschool` source
  block; `int_fldoe__all_assessments` goes back to
  `ref("stg_powerschool__students")`.
- `CLAUDE.md`: PowerSchool is an archive built from the package, not a native
  source.

The package builds about 120 models for Miami once. Dagster gives them the eager
table condition, but their upstream `src_*` sources emit no events, so nothing
rebuilds on its own. First and only materialization: Dagster UI,
`kippmiami_dbt_assets`, group `powerschool`. After that the tables rebuild only
when someone materializes them after a package change.

Building in place replaces the 2026-07-01 tables. The externals are the ground
truth and stay; a bad build is repaired by rebuilding. Columns may differ from
the frozen copies where the package changed since July; `union_relations`
intersects columns at run time, and PR 2's compile catches a consumer that named
a dropped column.

## kipptaf changes

- `sources-kippmiami.yml`: remove the 13 dropped tables from the
  `kippmiami_powerschool` source. Description changes from "never rebuilt" to
  "archive, rebuilt from the frozen externals by the kippmiami project".
- 13 unions: delete the `kippmiami` relation. `users`, `userscorefields`, `log`,
  `gen`, `fte`, `test`, `testscore`, `studenttest`, `studenttestscore`,
  `int_powerschool__spenrollments`, `int_powerschool__student_enrollment_union`,
  `int_powerschool__district_entry_date`,
  `int_powerschool__teacher_grade_levels`. No consumer wants Miami history from
  them; enrollment stints and district entry dates come from the Focus roster,
  which #4775 made the sole Miami source.
- 32 unions: unchanged. They keep `source("kippmiami_powerschool", X)` and now
  receive bounded, renumbered rows.
- Delete the Miami-only steps the package now performs:
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

## Filters

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

PR 1, `powerschool` package plus `kippmiami`: the 2 transforms, the package
re-include, the vars, the fldoe source swap. dbt Cloud CI builds kipptaf only,
so NJ parity is checked locally: build one NJ district's `stg_powerschool__*`
with `--target staging` and compare to prod. Then materialize the Miami archive
in prod before PR 2.

PR 2, `kipptaf`: everything under "kipptaf changes", filter groups 1 and 2, the
3 repoints. Depends on PR 1 materialized. Also touches `int_students__ada` and
`int_students__attendance_streak`, which PR #5188 (#5160) edits: merge #5188
first and delete its renumber here, or close #5188 as superseded because the
archive renumbers those tables. Decide before opening PR 2.

PR 3, `kipptaf`: filter group 3 conversions and `rpt_tableau__crdc_roster`.

## Verification

PR 1, before the Miami build, snapshot per frozen table:

```sql
select academic_year, count(*)
from `teamster-332318.kippmiami_powerschool.<table>`
group by 1 order by 1
```

After: row counts equal for AY2025 and earlier; 0 rows for AY2026 (today
`stg_powerschool__terms` carries 21 scaffold rows at `yearid >= 36`, and
`stg_powerschool__cc` carries 0); `countif(student_number < 8400000000)` is 0 on
`stg_powerschool__students`, `int_powerschool__ada`,
`int_powerschool__attendance_streak`, and
`int_powerschool__ps_adaadm_daily_ctod` (today all 3,946 students and 7,930 ADA
rows are bare). NJ: one district's staging models row-identical to prod with the
vars unset.

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

- Dropping the `kippmiami_powerschool` dataset or the GCS files under it. They
  are the archive's ground truth.
- Moving archive grades or attendance into Focus. Focus holds no real pre-AY2026
  attendance (`int_students__sis_cutover`).
- `int_students__fldoe_fte`: `enabled: false`, nothing refs it. Florida FTE
  reporting reads `int_students__student_enrollments`, not PowerSchool.
- The 8 kipptaf vendor-file callers of `focus_student_number`
  (`stg_renlearn__star`, `int_iready__*`, `int_amplify__mclass__*`). They
  renumber bare Miami ids from files, not from PowerSchool.
