# Newark PowerSchool 504 flag from EdPlan — design

Issue: #6423. Related: #6350 (EdPlan 504 report ingestion), #6354 (`is_504`
reads `PID_504_TF`).

## Why

Schools write 504 plans in EdPlan, but state reporting reads PowerSchool. TIDE,
the NJ SLA report, and the network `is_504` flag all read the PowerSchool state
field `S_NJ_STU_X.PID_504_TF`. Today the two systems disagree. Schools update
PowerSchool by hand, and most active plans never reach it.

The goal is for PowerSchool to match EdPlan every night, for Newark, without
anyone retyping 504 status.

## Goals

- Every night, Newark's student AutoComm file carries `PID_504_TF` for every
  student it already lists. A currently enrolled student gets 1 with an active
  EdPlan 504 plan and 0 without one. Withdrawn students, and every student on a
  night the EdPlan report has no active plans, get their current PowerSchool
  value back (_Write-back rule_).
- An active plan is an EdPlan event with
  `event_selector = 'Currently Valid: Section 504 Plan'` and an `end_date` of
  today or later, or no end date. "Today" is the day the file is written.
- The next day, `stg_powerschool__s_nj_stu_x.is_504` for those students matches
  EdPlan, and `int_students__student_enrollments.is_504` follows (#6354).

## Non-goals

- Camden and Paterson. Their EdPlan 504 report is not loaded.
- Eligibility determinations without an active plan. They do not count as a 504.
- `U_STUDENTSUSERFIELDS.C_504_STATUS`. Nothing reads it after #6370.
- Changing how `is_504` is derived. It already reads `PID_504_TF`.
- Any EdPlan data-quality fixes (lapsed "Currently Valid" plans, blank
  disability). The end-date rule handles the first; the second does not affect
  this field.

## Anti-goals

This fails even if the new column works, when any of these happens:

- Any existing column in Newark's students file moves or changes value. The
  PowerSchool import maps the headerless file by position.
- Camden's or Paterson's students file changes at all.
- A student appears twice in the file. EdPlan has one row per event, so a
  student with several events must still produce one row.
- "Today" freezes at a model build, so a plan that lapses stays on.
- A student who is not in today's file gets a value. The new column rides on the
  existing roster only.

## Constraints

- **File shape.** Newark's students file is tab-separated with no header row.
  Dagster writes it at 03:05 local from `kippnewark_extracts`
  (`src/teamster/code_locations/kippnewark/extracts/config/powerschool.yaml`),
  and PowerSchool AutoComm imports it at 03:30.
- **PowerSchool mapping.** The import maps these 20 targets, in this order, as
  of 2026-11-16: `student_number`, `student_web_id`, `student_web_password`,
  `student_allowwebaccess`, `web_id`, `web_password`, `allowwebaccess`, `team`,
  `track`, `LunchStatus`, `U_StudentsUserFields.lunch_balance`, `Home_Room`,
  `StudentCoreFields.graduation_year`, `DistrictEntryDate`, `SchoolEntryDate`,
  `S_NJ_STU_X.Retained_TF`, `S_NJ_STU_X.Graduation_Pathway_Math`,
  `S_NJ_STU_X.Graduation_Pathway_ELA`, `U_StudentsUserFields.studentemail`,
  `S_STU_X.FAFSA`. They line up 1:1 with the Newark wrapper's 20 columns. The
  user added `S_NJ_STU_X.PID_504_TF` as the 21st target on 2026-11-16, before
  this change ships (see _Rollout_).
- **Where logic lives.** Cross-region logic lives in kipptaf. The district
  wrapper is contract-columns-only and filters
  `code_location = '{{ project_name }}'` (`src/dbt/kipptaf/CLAUDE.md`,
  `extracts/powerschool/` special case).
- **How kipptaf reaches Newark data.** Only through a `sources-kippnewark.yml`
  entry plus a kipptaf `union_relations` pass-through model. kipptaf has no
  source for the EdPlan 504 report yet.
- **Freshness.** Both AutoComm models are views. The 03:05 extract reads them
  live, so "today" is evaluated then. The EdPlan 504 report has loaded at about
  08:40 local on recent days, so each night's file uses the previous day's
  EdPlan report.
- **CI.** dbt Cloud CI builds kipptaf only, reading district data from
  `zz_stg_<district>_*`. `zz_stg_kippnewark_edplan` has no copy of the 504
  report, so CI fails until one exists. The Newark wrapper change is
  district-only, so CI does not build it. A local build is its only check before
  merge.
- **PII.** 504 status is student-level PII. The file goes only to the AutoComm
  drop. GitHub gets aggregates with no cell under 10.

## Approaches

1. **New separate 504 file.** Two columns, its own PowerSchool import. It can be
   switched off on its own, but it means one more import to set up and run.
2. **A 21st column on the existing students file.** No new import, and the
   roster is already exactly the set of students to write. It touches the import
   that also sets web access, passwords, and lunch status, so column order must
   not move.
3. **Columns on the IEP file.** That file lists IEP students only, so it cannot
   carry the 0s.

**Chosen: 2**, by the user on 2026-11-16. The user also set up the PowerSchool
side for it.

## Design

### Decided by the user

- Newark only, through the students AutoComm, as a 21st column.
- Target `S_NJ_STU_X.PID_504_TF`.
- Active plans only, by the end-date rule in _Goals_.
- Mirror EdPlan: 1 for an active plan, 0 for everyone else in the file.

### Proposed calls

- **Position.** `s_nj_stu_x__pid_504_tf` is the last column of the Newark
  wrapper, so the first 20 positions do not move.
- **Roster.** The students file's existing roster:
  `int_extracts__student_enrollments`, current academic year, `rn_year = 1`,
  `grade_level != 99`. The column adds no rows and removes none. Only currently
  enrolled students (`enroll_status = 0`) get a 1 or 0, since the user asked for
  "every current Newark student". Withdrawn students' rows write back their
  current value (_Write-back rule_).
- **Edge cases in the active-plan rule.** A plan whose `begin_date` is in the
  future, or a plan beside a later Currently Valid non-eligibility
  determination, still counts under the rule as stated. Neither case existed on
  2026-11-16, so the rule stays as the user set it.
- **Values.** `int64` 1 or 0, the same form as `retained_tf`.
- **Data path.**
  1. Add `stg_edplan__section_504_student_report` to
     `src/dbt/kipptaf/models/edplan/sources-kippnewark.yml`, with its Dagster
     asset key `[kippnewark, edplan, stg_edplan__section_504_student_report]`.
  2. Add a kipptaf `union_relations` pass-through over that source, with a
     model-level `contains_pii` tag (kipptaf wrappers re-declare the tag). It
     unions Newark only today. Camden or Paterson join the union when their
     report loads.
  3. Roll the events up to one row per student and region, with a flag for an
     active plan. The end-date rule needs `current_date`, so the rollup must be
     a view, or the flag must be computed in the AutoComm model itself, never in
     a table.
  4. In kipptaf `rpt_powerschool__autocomm_students`, left join the rollup on
     `student_number` and `_dbt_source_project`. Emit 1 or 0 for Newark rows and
     null for every other region.
  5. Newark's wrapper selects the new column last. Camden's and Paterson's
     wrappers do not change.
- **Camden and Paterson.** The kipptaf column is null for them, and their
  wrappers never select it, so their files stay byte-for-byte the same.

### Expected effect

Measured 2026-11-16 against prod, with today's EdPlan report:

| Measure                                            | Count |
| -------------------------------------------------- | ----: |
| Newark students in the file                        | 6,784 |
| Would be written 1                                 |   135 |
| Active-plan students missing from the file         |     0 |
| Flagged in PowerSchool today, students in the file |    86 |
| Would turn on (0 → 1)                              |    83 |
| Would turn off (1 → 0), currently enrolled         |    28 |

Fewer than 10 of the 28 have no 504 record in EdPlan at all. If withdrawn
students also got a 0, 34 would turn off.

## Rollout

1. **CI staging copy.** Before the PR's CI runs, seed
   `zz_stg_kippnewark_edplan.stg_edplan__section_504_student_report` from prod
   with `dbt clone --target staging --full-refresh`. That is a write to the
   shared staging datasets, so it needs the user's go-ahead at the time. The
   main checkout's prod manifest predates the model, and a clone skips any node
   its state manifest lacks. Regenerate the Newark prod manifest first with
   `uv run dbt parse --target prod`.
2. **Before the first import.** Send the list of students who would turn off to
   Felicia Harris and Kara Brockett as a restricted Google Sheet. The user
   decided on 2026-11-16 that this is a heads-up, not a gate: the change goes
   live on merge, and EdPlan corrections flow through the next night.
3. **Deploy order.** After merge, Dagster must rebuild the kipptaf model before
   the Newark wrapper view, because the wrapper selects the new column. Check
   that both rebuilt before the next 03:05 run.
4. **First night.** Check the file landed with 21 columns and 6,784-ish rows.
   The next day, check `PID_504_TF` in prod against the active-plan list.

**Live risk until this ships.** The PowerSchool import already has the 21st
target, and the file has 20 columns until this ships. The user confirmed on
2026-11-16 that a blank or missing column clears the field. So every nightly
import before go-live clears `PID_504_TF` for every student in the file, unless
the 21st target comes off first.

**A blank clears.** No row may carry a blank in the new column. That rules out
"blank means leave alone" for withdrawn students and for a bad EdPlan night; see
_Write-back rule_. At 10:42 ET on 2026-11-16, prod showed 261 flagged rows
across all of Newark's `S_NJ_STU_X` records, past students included, and 86
among the students in the file. Those are the baselines for checking the next
import.

## Write-back rule

Approved by the user on 2026-11-16. A blank clears the field, so "leave it
alone" means writing back the value PowerSchool already holds:
`stg_powerschool__s_nj_stu_x.is_504` from the last pull, as 1 or 0. Each Newark
row takes the first branch that matches:

```sql
case
    when not edplan_has_any_active_plan then current_pid_504_tf
    when enroll_status != 0 then current_pid_504_tf
    when has_active_504_plan then 1
    else 0
end as s_nj_stu_x__pid_504_tf
```

- `edplan_has_any_active_plan` is one value for the whole Newark report each
  night. It guards against a bad EdPlan file: the 504 asset reloads only when a
  newer file lands on the SFTP, and it loads an empty or 0-row file with a
  warning, replacing the last good load
  (`src/teamster/libraries/sftp/assets.py`). In the month to 2026-11-16, the
  NJSMART export from the same SFTP loaded 60 times, between 1,127 and 1,141
  records each, so this is rare.
- Withdrawn students (`enroll_status != 0`) write back their current value, so
  this change never alters their records.
- For a currently enrolled student, `has_active_504_plan` is false when EdPlan
  has no matching row. It is never a `coalesce` to the PowerSchool value, which
  would keep students on that EdPlan says are off.
- An unset `PID_504_TF` writes back as 0. The field defaults to No, so the
  meaning does not change.
- If staff change a withdrawn student's 504 box between the daily PowerSchool
  pull and the 03:30 import, the write-back reverts it to the pulled value.
  Accepted as a narrow window.

## Verification

- dbt Cloud CI passes on the kipptaf models.
- On the CI build, Newark rows of `rpt_powerschool__autocomm_students`:
  - The row count equals prod's for the same day.
  - The 1s equal the active-plan count.
  - No `student_number` repeats.
- Camden and Paterson rows have a null in the new column.
- A dbt unit test covers each branch of the write-back rule: no active plans in
  the report, a withdrawn student, a currently enrolled student with an active
  plan, and one without.
- On the CI build, every withdrawn Newark row's new column equals that student's
  current PowerSchool value.
- A local build of the Newark wrapper has 21 columns, the first 20 matching
  prod's wrapper value for value.
- The day after the first import, current Newark `is_504` in prod equals the
  active-plan list, give or take that day's changes.

## Left to the builder

- The names of the pass-through and the rollup, and whether the rollup is its
  own model or a CTE in the AutoComm model.
- Tests. kipptaf `rpt_powerschool__autocomm_students` has no data tests today,
  and the repo rule (#5990) adds a grain test at `error` to any `rpt_` a PR
  modifies. It must return 0 rows in prod first; Newark rows had no repeated
  `student_number` on 2026-11-16. Add whatever else proves the rollup has one
  row per student.
- Column descriptions.

## Revision 2026-11-17: 504 status dimension

Decided by Charlie Bini in review of #6424. Replaces _Data path_ steps 3 and 4.
Everything else above stands: the file shape, the write-back rule, the rollout,
and the verification.

### Why

The first build read EdPlan through two new intermediates. That left 2 problems.
`int_students__section_504_status` shared its grain with
`int_students__students` (A4). And the `rpt_` read an intermediate because no
mart carried 504 plans (A2, #6425). This revision adds the mart, so both go
away, and #6425 closes with this PR.

### Goals

- A new mart, `dim_student_504_status`, holds each student's EdPlan 504 plans as
  time windows, matched to enrollment stints. It follows _SCD2 status dims bound
  to enrollments_ in `src/dbt/kipptaf/models/marts/CLAUDE.md`, as
  `dim_student_iep_status` does.
- `rpt_powerschool__autocomm_students` reads the dim for the EdPlan side and the
  roster's existing `is_504` for PowerSchool's value. No new A1 edge and no new
  A2 edge.
- For every student in the file today, the new column's value is identical to
  the first build's. The only planned difference is _Stint alignment_.

### Non-goals

- Changing what counts as an active plan. The rule in _Goals_ above stands.
- A freshness policy on the EdPlan 504 asset. `libraries/edplan/freshness.py`
  covers only `stg_edplan__njsmart_powerschool`. That is a separate Dagster
  change.
- Eligibility and non-eligibility determinations. Plans only.
- Camden and Paterson. Their reports are not loaded, so the dim has no rows for
  them.

### Anti-goals

- Today's date inside a mart. A mart may be stored as a table, which would
  freeze "today" at its build time. The dim stores dates. Only the `rpt_` view
  compares them to today.
- A previous plan counting as active. EdPlan lists 3 previous plans with no
  later plan and an end date still in the future (2026-11-17). Matching on dates
  alone would turn those students on.
- A row fan-out in the extract. At most 1 dim row may match each student in the
  file.

### Approaches

1. **Domain intermediate, then the dim (chosen).** A students-folder
   intermediate builds the plan windows from the kipptaf EdPlan union. The dim
   reads it and the enrollment union. Both reads are allowed edges.
2. **The dim reads the EdPlan source model directly.** That is a new A1
   violation. `dim_student_iep_status` does this, but it sits in
   `standard-baseline.tsv` as an existing violation, not a pattern to copy.
3. **Plan logic in an `edplan/` source intermediate.** A mart cannot read a
   source `int_`, so this needs a second pass-through model.

Also decided: history covers both current and previous plans (option 1 of 2,
over current plans only), so the dim is a real history and follows the
enrollment-bound pattern.

### Design

#### Models

| Model                                        | Change                   |
| -------------------------------------------- | ------------------------ |
| `stg_edplan__section_504_student_report`     | Keep (kipptaf union)     |
| `int_edplan__section_504_active_plan_rollup` | Delete (never shipped)   |
| `int_students__section_504_status`           | Delete (never shipped)   |
| `int_students__section_504_plans`            | New, students folder     |
| `dim_student_504_status`                     | New, `marts/dimensions/` |
| `rpt_powerschool__autocomm_students`         | Read the dim instead     |

#### `int_students__section_504_plans`

One row per student, region, and plan start date. It reads the kipptaf
`stg_edplan__section_504_student_report`.

- Keep rows where `event_selector` is `Currently Valid: Section 504 Plan` or
  `Previous: Section 504 Plan`, and `student_number` is not null.
- `is_current_plan`: true for the Currently Valid selector.
- `plan_start_date`: `begin_date`. `not_null` test at `error`. None are null on
  2026-11-17, and a null would break the grain key. (Builder's call.)
- `plan_end_date`: for a current plan, its `end_date`, or `9999-12-31` when
  null, as the rule in _Goals_ counts a plan with no end date (builder's call;
  none are null on 2026-11-17). For a previous plan, the earlier of its
  `end_date` and the day before the student's next plan begins. The next plan is
  the next row by `begin_date` for the same student and region. When a previous
  and a current plan share a `begin_date`, the current plan sorts later.
- Drop a previous plan whose `plan_end_date` falls before its `plan_start_date`.
  That is a plan replaced on the day it began.
- Never cut a current plan. One student on 2026-11-17 has a previous plan that
  begins after their current plan. Cutting would change their result.
- No `current_date`. Grain test at `error` on student number, region, and
  `plan_start_date`.

#### `dim_student_504_status`

Copies the enrollment-matching part of `dim_student_iep_status` (its
`enrollments` CTE and `nj_leg`). It does not need the island-grouping CTEs,
because each plan is already one window.

- Inner join plans to `int_students__student_enrollment_union` stints on student
  number and region where the windows overlap. Start is the later of plan start
  and stint entry. End is the earlier of plan end and the stint's last day.
- Columns: `student_504_status_key` (PK: student number, region, window start,
  as the IEP dim), `student_key` (`student_key` macro), `student_enrollment_key`
  (`student_enrollment_key` macro), `_dbt_source_project`,
  `effective_date_start_key`, `effective_date_end_key`, `is_current_plan`.
- No `is_current` column. Every EdPlan plan has an end date, so the IEP dim's
  `9999-12-31` test would never be true. `is_current_plan` carries EdPlan's own
  status instead.
- View, the marts default. FK edges and constraints per
  `src/dbt/kipptaf/models/marts/CLAUDE.md`. Add the dim to
  `cube_semantic_layer.depends_on` in `cube.yml`. No Cube view reads it yet.

#### PowerSchool's value

The write-back rule's `current_pid_504_tf` is `if(se.is_504, 1, 0)` from the
roster, `int_extracts__student_enrollments`, which the `rpt_` already reads. No
new column anywhere. Decided by Charlie Bini, over a column on `dim_students` or
`int_students__students`.

- The roster's `is_504` reads the past-enrollment record (`S_NJ_REN_X`) before
  `S_NJ_STU_X`. On 2026-11-17 it equals `S_NJ_STU_X` for all 6,789 Newark rows
  in the file, withdrawn included.
- Accepted risk: PowerSchool copies a student's 504 value onto the
  past-enrollment record at withdrawal. If staff change a withdrawn student's
  504 box afterward, the file writes the old value back. The column description
  says so.

#### `rpt_powerschool__autocomm_students`

- Build `student_enrollment_key` from the roster row with the macro, and left
  join the dim on it, with `is_current_plan`,
  `effective_date_start_key <= current_date(...)`, and
  `effective_date_end_key >= current_date(...)` in the join.
- `has_active_504_plan` is "a dim row matched". At most 1 row matches, because
  each student has at most 1 current plan (2026-11-17), and the join is to 1
  stint.
- The region guard counts the dim rows that pass the same filter, per region.
- `current_pid_504_tf` comes from the roster (_PowerSchool's value_).
- The write-back `case` is unchanged.

A current-year stint has an exit date (every Newark stint for 2026 exits
2027-06-30 on 2026-11-17), so the window ends at the earlier of the plan's end
and the stint's last day. That end is still today or later whenever the plan's
own end is. The result matches the first build except for a plan that has not
started yet; see _Stint alignment_.

The known odd student (a previous plan beginning after the current plan) does
not collide on the dim's key: neither plan is cut to the same stint entry date
(checked 2026-11-17).

### Verification

- Unit tests:
  - The plans intermediate: a previous plan cut by a later plan; a previous plan
    dropped by a shared start date; a current plan left uncut; an eligibility
    row dropped.
  - The dim: a plan spanning 2 stints yields 2 windows; a plan outside every
    stint yields none.
  - The `rpt_`: the 4 write-back branches stay as they are; a previous plan
    whose end date has not passed yields 0; a current plan that starts after
    today yields 0.
- Against prod, the new `rpt_` column equals the first build's for every Newark
  row. Every `student_enrollment_key` from the roster that should match does.
- `dbt-layer-check` passes, with no new baseline rows and no A4 warning from
  this PR.

### Stint alignment

Decided by Charlie Bini. A plan counts from its start date to its end date, and
only on days inside an enrollment stint. This replaces the rule in _Goals_ and
_Edge cases in the active-plan rule_ above, which counted a plan before its
`begin_date`. For a student's current stint, the file writes 1 when a current
plan's window, cut to that stint, includes today.

Examples for a stint entered 2026-09-01 with exit date 2027-06-30 (last day
2027-06-29):

| Plan                     | Counts in this stint     | Tonight (2026-11-17) |
| ------------------------ | ------------------------ | -------------------- |
| 2026-03-01 to 2027-03-01 | 2026-09-01 to 2027-03-01 | 1                    |
| 2026-10-01 to 2027-10-01 | 2026-10-01 to 2027-06-29 | 1                    |
| 2027-01-15 to 2028-01-15 | 2027-01-15 to 2027-06-29 | 0                    |
| 2027-09-01 to 2028-09-01 | Never (next stint only)  | 0                    |
| 2025-09-01 to 2026-10-31 | 2026-09-01 to 2026-10-31 | 0                    |

A plan that crosses the summer applies to both stints, as 2 dim rows. No current
plan starts after 2026-11-17, so the first night's file is unchanged.

### Left to the builder

- Unit-test fixtures and column descriptions. Mart descriptions say what a value
  means, not where it comes from (`marts/CLAUDE.md`).
- If the dim's grain test fails on prod data, stop and report. Do not add a
  dedup.
