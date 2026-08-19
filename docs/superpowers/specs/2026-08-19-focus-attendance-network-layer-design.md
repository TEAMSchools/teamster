# Focus attendance in the kipptaf network layer: SIS-neutral attendance models

Issue: [#4924](https://github.com/TEAMSchools/teamster/issues/4924)

## Problem

Miami has been in session since 2026-08-12 and contributes zero attendance rows
to the kipptaf network layer. Focus holds the data, the Miami-side intermediates
shipped in [#4919](https://github.com/TEAMSchools/teamster/pull/4919), and
nothing at kipptaf level consumes them.

Verified against prod on 2026-08-19:

| Check                                                  | Result                                       |
| ------------------------------------------------------ | -------------------------------------------- |
| Miami rows in `int_powerschool__ps_adaadm_daily_ctod`  | stops at AY2025 (229,463 rows); 0 for AY2026 |
| Focus branch in `kipptaf/models/powerschool/`          | none — `grep -rl focus` returns nothing      |
| `int_focus__attendance_day` rows                       | 9,253, all AY2026                            |
| `int_focus__attendance_day` in `sources-kippmiami.yml` | absent, and no kipptaf wrapper               |

Everything downstream reads empty for Miami: `fct_student_attendance_daily`,
`fct_student_attendance_streaks`, `fct_student_attendance_interventions`,
`dim_school_calendars`, and (transitively, through
`int_powerschool__calendar_week`) `bridge_survey_expectations`. Miami ADA,
chronic absenteeism, and topline Total Enrollment all understate the network.

## Two corrections to the issue's plan

### The issue's model list is at the wrong altitude

`int_powerschool__ada` and `int_powerschool__attendance_streak` are computed in
the **district** project, over the district's own
`int_powerschool__ps_adaadm_daily_ctod`. kipptaf's wrapper of that model is a
filtered subset of it — the inner joins to `int_students__terms` and
`int_powerschool__calendar_week` drop 29% of rows:

| Relation                                                       | Newark rows |
| -------------------------------------------------------------- | ----------- |
| `kippnewark_powerschool.int_powerschool__ps_adaadm_daily_ctod` | 13,990,042  |
| `kipptaf_powerschool.int_powerschool__ps_adaadm_daily_ctod`    | 9,942,287   |

Recomputing `streak_id` at network altitude reproduces 2,293,675 of 2,415,982
hashes, so 5% would churn, and ADA denominators would move by the full 29%.
Those two models therefore get their Focus branch in the `focus` package, at the
same altitude PowerSchool derives them — not at kipptaf.

### Phase 1's exclusion rule does not transfer

`int_students__terms` drops Miami from the PowerSchool side wholesale
(`where _dbt_source_project != 'kippmiami'`) because Focus is the system of
record for terms in every year. Attendance is different: Focus starts at AY2026
and the frozen archive holds Miami AY2020 through AY2025. A project-level
exclusion would delete six years of Miami attendance history, contradicting the
issue's own scope boundary.

The union is **year-scoped** instead, and the boundary is **derived from the
years Focus actually covers** rather than hardcoded. That is self-maintaining as
Focus accumulates years, and it fails loudly rather than double-counting if
Focus ever backfills a historical year.

## Architecture

The `focus` package builds the Focus analogues at PowerSchool's own altitude.
kipptaf does nothing but thin unions. The existing `int_powerschool__*` wrappers
stay as pure PowerSchool unions.

```text
focus package                       kipptaf sources          kipptaf SIS-neutral
─────────────                       ───────────────          ───────────────────
int_focus__attendance_daily    ──▶  sources-kippmiami   ──▶  int_students__attendance_daily
int_focus__ada                 ──▶  sources-kippmiami   ──▶  int_students__ada
int_focus__attendance_streak   ──▶  sources-kippmiami   ──▶  int_students__attendance_streak
int_focus__calendar_week       ──▶  sources-kippmiami   ──▶  int_students__calendar_week
int_focus__calendar_rollup     ──▶  sources-kippmiami   ──▶  int_students__calendar_rollup
int_focus__calendar_day        ──▶  sources-kippmiami   ──▶  int_students__calendar_day
```

Why this altitude and not the alternatives:

- Deriving `ada` / `attendance_streak` / `calendar_week` at kipptaf over the
  SIS-neutral union changes NJ, per the 29% finding above.
- Building the Focus branch in `kippmiami` rather than the `focus` package costs
  nothing today (`focus` has exactly one consumer,
  `grep -l 'local: ../focus' src/dbt/*/packages.yml`), but
  `int_focus__student_enrollment` already carries a TODO about a second Focus
  region onboarding, and district-local models do not travel when that happens.

### The id boundary

The `focus` package **cannot** resolve the network school id. That hop runs
through `stg_google_sheets__people__locations` on `focus_school_id` (the Florida
code, e.g. `2332C`), and the locations sheet is a kipptaf model, unreachable
from a package.

So the package models emit Focus's internal `schoolid` (14, 15, 58, 68, 69) and
the kipptaf union layer does the crosswalk, exactly as `int_students__terms`
already does in its `focus_schools` CTE. Student ids need no crosswalk —
`network_student_number` is a prefix strip that `int_focus__student_enrollment`
performs in-package.

The crosswalk is complete for every school that matters: 7 Miami rows in the
locations sheet mapping `2008A`/`2008B`/`2008Z`/`2332A`/`2332B`/`2332C`/`2332D`
to `powerschool_school_id` 30200801 through 30200807. The three
non-instructional Focus schools (`Applicants`, `Virtual Franchise`,
`ZZ Course History`) have no locations row and drop out on the join, which is
the existing Phase 1 behavior.

## `int_focus__attendance_daily`

The load-bearing new model, and the analogue of the district
`int_powerschool__ps_adaadm_daily_ctod`.

Grain: one row per enrolled student per in-session calendar day. Built as
enrollment crossed with in-session calendar days, left-joined to
`int_focus__attendance_day`.

The scaffold is necessary because a missing attendance record is not visible at
`int_focus__attendance_day`'s own grain. Measured for AY2026: 9,287 scaffold
rows against 9,253 attendance rows, joining to 9,163 matched, 124 scaffold days
with no record, and 90 attendance rows outside any scaffold row. So Focus is
already about 99% complete daily coverage, not sparse — but the scaffold is what
makes an un-recorded day representable at all.

### Column contract

| District ctod column                   | Focus source                                 | Note                                                                      |
| -------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------- |
| `studentid`                            | —                                            | null, consistent with Phase 1's enrollment union                          |
| `student_number`                       | `network_student_number`                     | unprefixed network number                                                 |
| `schoolid`                             | Focus internal `schoolid`                    | crosswalked at kipptaf, not here                                          |
| `entrydate`                            | enrollment `startdate`                       |                                                                           |
| `calendardate`                         | `stg_focus__attendance_calendar.school_date` |                                                                           |
| `yearid`                               | `academic_year - 1990`                       | the verified network formula                                              |
| `grade_level`                          | enrollment `grade_level`                     |                                                                           |
| `att_code`                             | mapped Focus code                            | see the mapping below                                                     |
| `attendancevalue`                      | `state_value`                                | already the present/absent classification                                 |
| `potential_attendancevalue`            | `1`                                          | every membership day is potentially attendable                            |
| `membershipvalue`                      | `1`                                          | every in-session day within the stint                                     |
| `fteid`                                | —                                            | null. Focus's own `fteid` is a student FLEID, an unrelated name collision |
| `attendance_conversion_id`             | —                                            | null, PowerSchool-specific                                                |
| `ontrack`, `offtrack`, `student_track` | —                                            | null. Passthrough columns at kipptaf, never used in a calc                |

### Attendance code mapping

Focus's day-grain vocabulary is four codes. PowerSchool's is twelve. They nearly
coincide:

| Focus     | Focus meaning     | Maps to | PowerSchool meaning                       |
| --------- | ----------------- | ------- | ----------------------------------------- |
| null      | present           | null    | present                                   |
| `U`       | Absent Unexcused  | `A`     | Absent Undocumented / Absent              |
| `AE`      | Absent Excused    | `AE`    | Absent Excused — exact match              |
| `AD`      | Absent Documented | `AD`    | Absent Documented — exact match           |
| no record | —                 | `M`     | Missing Attendance, `attendancevalue = 1` |

`AE` and `AD` match exactly, so only `U` needs renaming. That makes every
existing consumer predicate correct for Miami with **zero consumer branching** —
`att_code like 'A%'`, `att_code like 'T%'`, and
`att_code in ('OS', 'OSS', 'OSSP', 'SHI')` all behave as intended.

Mapping `U` is not cosmetic: `U` already exists in the PowerSchool vocabulary
meaning **Unprepared** (14 rows), an unrelated concept. Passing Focus codes
through unmapped would silently merge unexcused absences into it.

The raw Focus code is retained in its own column so nothing is lost.

The `M` mapping matches PowerSchool's own semantics — the district ctod resolves
a day with no absence record to the `Present` conversion, so a missing record
counts as present. Using the in-vocabulary `M` code keeps those 124 days flagged
rather than buried.

## Deferred, tracked elsewhere

### Six flags land null for Miami

`is_tardy`, `is_ontime`, `is_oss`, `is_iss`, `is_suspended`, and
`is_absent_non_susp` have no Focus day-grain source.

Focus day grain carries no tardy code; tardies exist only at period grain (528
AY2026 rows titled `Tardy`, state code `P`). Suspensions exist nowhere in Focus
attendance at any grain.

Null rather than zero, so Miami is excluded from network tardy and suspension
metrics rather than diluting them with false zeros. Tracked in
[#4927](https://github.com/TEAMSchools/teamster/issues/4927), marked in place
with a `TODO(#4927)` comment at each null.

### Focus calendar misconfiguration

Five of Miami's ten Focus schools carry a 212-day AY2026 attendance calendar
instead of 182, including Labor Day, Thanksgiving, Christmas, New Year's Day,
and all ten winter-break weekdays. All five have zero AY2026 enrollments. Every
one of the ten calendars is flagged `default_calendar = Y`, so that flag cannot
distinguish a real calendar from an unconfigured one.

| Focus school | Name                                | Days |
| ------------ | ----------------------------------- | ---- |
| 60           | Applicants                          | 212  |
| 62           | Virtual Franchise (7023)            | 212  |
| 70           | ZZ Course History (9999)            | 212  |
| 71           | KIPP MIAMI SUNRISE ACADEMY (Closed) | 212  |
| 72           | KIPP MIAMI-LIBERTY CITY (Closed)    | 212  |

This is a Focus configuration problem, not a modeling one, so it is **not
filtered in a model**. It is handed to Ops as an
[Asana task](https://app.asana.com/1/913513768672/project/1205971774138578/task/1217643843838185).

Consequence accepted until Ops fixes it: the three junk schools have no
locations-sheet row and drop out on their own, but the two closed schools map to
live location keys, so the Focus branch of `dim_school_calendars` will report
their holidays as in-session days. Both are closed with zero students, so no
metric moves. A warn-severity test surfaces the rows rather than hiding them.

## kipptaf restructure

`int_powerschool__ps_adaadm_daily_ctod` becomes a **thin union wrapper** —
`union_relations` plus `_dbt_source_project`, nothing else. Its roughly 200
lines of derived flags, anchors, and running calcs move unchanged to
`int_students__attendance_daily`.

Leaving the calcs in place would force the Focus branch to duplicate them.
Moving them gives one definition over the union. NJ is unaffected because every
window partition in those calcs is already scoped by `_dbt_source_project`, so
computing post-union is arithmetically identical to computing per-branch.

Year-scoping reads `yearid` off the district rows, so the thin wrapper needs no
terms join:

```sql
focus_years as (select distinct yearid from {{ ref("int_focus__attendance_daily") }}),

powerschool_conformed as (
    select *
    from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
    where not (
        _dbt_source_project = 'kippmiami'
        and yearid in (select yearid from focus_years)
    )
)
```

### Consumer repoints

37 refs across 32 distinct files move:

| From                                      | To                                | Refs |
| ----------------------------------------- | --------------------------------- | ---- |
| `int_powerschool__ps_adaadm_daily_ctod`   | `int_students__attendance_daily`  | 11   |
| `int_powerschool__calendar_week`          | `int_students__calendar_week`     | 17   |
| `int_powerschool__calendar_rollup`        | `int_students__calendar_rollup`   | 3    |
| `int_powerschool__attendance_streak`      | `int_students__attendance_streak` | 2    |
| `int_powerschool__ada`                    | `int_students__ada`               | 1    |
| `stg_powerschool__calendar_day`           | `int_students__calendar_day`      | 1    |
| `stg_powerschool__attendance` and `_code` | `int_students__attendance_daily`  | 2    |

Two files reference `int_powerschool__calendar_week` twice, and one of its
consumers is `int_powerschool__ps_adaadm_daily_ctod` itself — that ref moves
with the calcs into `int_students__attendance_daily` rather than being edited in
place.

Deliberately left alone: `rpt_tableau__powerschool_calendar_day`,
`rpt_tableau__staff_attendance`, and `int_google_sheets__dibels_pm_expectations`
keep reading `stg_powerschool__calendar_day`. The first is a PowerSchool extract
by name and intent; staff attendance has no Focus analogue.

### Two join keys change

`studentid` is null on all 10,047 Miami rows of
`int_students__student_enrollment_union` — Phase 1 never populated it. Any join
on `studentid` therefore excludes Miami by construction, which is a second,
independent reason Miami reads empty today.

Both affected joins move to `student_number`:

- `fct_student_attendance_streaks` — `st.studentid = enr.studentid` becomes
  `student_number`, including the `TODO(#4835)` dedupe partition
- `rpt_tableau__attendance_chronic_absenteeism_log` — rewritten onto
  `int_students__attendance_daily`, keeping `att_code like 'A%'` (correct for
  Miami via the `U` mapping) and joining on `student_number`

The repoint is safe for NJ: `studentid` and `student_number` are strictly 1:1 in
every NJ region, verified by identical distinct counts and pair counts — Newark
18,148, Camden 5,510, Paterson 1,051. So the change can neither fan out nor drop
a row.

## Validation

### NJ parity, blocking

For each new `int_students__*` model against its `int_powerschool__*`
predecessor, NJ rows only:

- `count(*)` per `_dbt_source_project`
- `count(distinct format('%T|%T|...', ...))` on the key columns
- for `attendance_daily`, also `sum(membershipvalue)`, `sum(attendancevalue)`,
  and `sum(is_absent)` per project and academic year

### Miami presence

- `int_students__attendance_daily` carries Miami rows from 2026-08-12 forward,
  where there are 0 today
- `fct_student_attendance_daily` reports Miami for AY2026 and Miami ADA is
  non-null
- row count reconciles to roughly 1,559 enrolled students times elapsed
  in-session days

### dbt tests

- `unique` and `not_null` on
  `(student_number, _dbt_source_project, calendardate)` for
  `int_students__attendance_daily`. This grain is real today: AY2025 has
  1,886,156 rows and 1,886,156 distinct triples, which is what
  `fct_student_attendance_daily`'s `student_attendance_daily_key` already
  assumes
- warn: Focus scaffold days with no attendance record — 124 of 9,287 now, 1.3%
- warn: Focus attendance rows dropped by the scaffold — 90 now
- warn: Focus in-session days at a school with zero enrollment for that year.
  This is the test that surfaces the Ops calendar item

### Graph and issue hygiene

- `dbt build --empty` across the descendant graph
- re-measure the [#4803](https://github.com/TEAMSchools/teamster/issues/4803)
  orphan count and record the new number there. Focus carries AY2026-27 forward
  only, so this restores Miami's current year and does not re-key the AY2025
  archive rows — expect that orphan count to move, not vanish

## Ship sequence

Two PRs, in order. The package model must materialize in prod before kipptaf
reads it.

### PR1 — focus package

The six models plus properties and unit tests.

Its only real validation is a local build:

```bash
uv run dbt build --select int_focus__attendance_daily+ \
  --project-dir src/dbt/kippmiami --defer \
  --state src/dbt/kippmiami/target/prod --target dev
```

dbt Cloud CI builds `kipptaf` alone, so a package-only PR selects zero modified
models and its check goes green trivially, not as validation. Merge, then wait
for Dagster to materialize all six in prod.

### PR2 — kipptaf

Six source entries with Dagster asset keys, the six `int_students__*` models,
the wrapper strip, 33 consumer repoints, and the two join-key changes.

Before pushing, refresh the staging copies or CI reads a stale
`zz_stg_kippmiami_focus` and fails deterministically:

```bash
uv run dbt clone --select int_focus__attendance_daily int_focus__ada \
  int_focus__attendance_streak int_focus__calendar_week \
  int_focus__calendar_rollup int_focus__calendar_day \
  --target staging --state src/dbt/kippmiami/target/prod \
  --project-dir src/dbt/kippmiami
```

That command recreates shared `zz_stg_*` tables, so it needs direct user
authorization and is run by the user, not by Claude.

## Out of scope

- The AY2025 and earlier Miami archive rows are not re-keyed.
  [#4803](https://github.com/TEAMSchools/teamster/issues/4803) still needs a
  separate answer for its historical leg.
- Miami tardy and suspension sourcing, tracked in
  [#4927](https://github.com/TEAMSchools/teamster/issues/4927).
- The Focus calendar cleanup, handed to Ops.
- `int_focus__attendance_period` gains no kipptaf consumer here. It is declared
  as a source only if the tardy work in #4927 needs it.
