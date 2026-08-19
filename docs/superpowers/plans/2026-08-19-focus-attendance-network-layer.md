# Focus Attendance in the kipptaf Network Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Miami AY2026 attendance a path into the kipptaf network layer so
Miami ADA, chronic absenteeism, and Total Enrollment stop understating the
network.

**Architecture:** The `focus` package builds Focus analogues of the six
PowerSchool attendance models at PowerSchool's own altitude. kipptaf declares
each as a source, wraps it in a `union_relations` passthrough, and unions it
with the existing `int_powerschool__*` wrapper in a new SIS-neutral
`int_students__*` model. The PowerSchool branch is year-scoped so the frozen
Miami archive keeps serving AY2020 through AY2025 while Focus serves AY2026
forward.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, `uv`, trunk, Dagster.

Design spec:
[`docs/superpowers/specs/2026-08-19-focus-attendance-network-layer-design.md`](../specs/2026-08-19-focus-attendance-network-layer-design.md)

## Global Constraints

- Worktree is
  `/workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer`.
  Use `git -C <worktree>` on every git call and
  `--project-dir <worktree>/src/dbt/<project>` on every dbt call.
- Always `uv run` — never bare `python`, `dbt`, or `dagster`.
- Focus package models cannot `ref()` a kipptaf model. The network school id
  crosswalk (`stg_google_sheets__people__locations`) is kipptaf-only, so package
  models emit Focus's internal `schoolid` and kipptaf crosswalks it.
- Column types must match the kipptaf ctod exactly or the union fails:
  `studentid`, `student_number`, `schoolid`, `fteid`,
  `attendance_conversion_id`, `grade_level`, `ontrack`, `offtrack`, `yearid` are
  `INT64`; `att_code` and `student_track` are `STRING`; `entrydate` and
  `calendardate` are `DATE`; `attendancevalue`, `potential_attendancevalue`, and
  `membershipvalue` are `FLOAT64`.
- `int_focus__attendance_day.state_value` is `NUMERIC` — cast to `FLOAT64`.
- `int_focus__student_enrollment.student_number` is the **prefixed** Focus id
  (`8400…`); `network_student_number` is the stripped network number. Attendance
  joins on the prefixed form; output uses the stripped form.
- Attendance code mapping: `U` → `A`, `AE` → `AE`, `AD` → `AD`, null → null, no
  record → `M`. Never pass `U` through — `U` means Unprepared in PowerSchool.
- Six flags stay null for Miami (`is_tardy`, `is_ontime`, `is_oss`, `is_iss`,
  `is_suspended`, `is_absent_non_susp`), each marked `TODO(#4927)`.
- Never hash `studentid` on the Focus side. It is null, and
  `generate_surrogate_key` maps null to a constant, which would collapse every
  Focus student into one streak.
- Materialization overrides go in `properties/<model>.yml` as
  `config: materialized:`, never inline `{{ config() }}`.
- Fenced code blocks in any `.md` need a language (MD040). Backtick every
  `snake_case` identifier in prose.
- Do not run `trunk fmt`. Run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <paths> </dev/null`
  with cwd set to the worktree before any push.

## File Structure

### PR1 files — `focus` package

All paths below are relative to `src/dbt/focus/models/intermediate/`.

| File                                                           | Responsibility                                              |
| -------------------------------------------------------------- | ----------------------------------------------------------- |
| `int_focus__attendance_daily.sql`                              | Daily membership scaffold; the ctod analogue                |
| `int_focus__ada.sql`                                           | Per-student-year ADA rollup                                 |
| `int_focus__attendance_streak.sql`                             | Code and attendance-value streaks                           |
| `int_focus__calendar_day.sql`                                  | Per-school-day calendar with in-session flag                |
| `int_focus__calendar_week.sql`                                 | Per-school-week rollup with quarter context                 |
| `int_focus__calendar_rollup.sql`                               | Per-school-year instructional day totals                    |
| `properties/int_focus__attendance_daily.yml` and five siblings | Descriptions and data tests                                 |
| `unit_tests.yml`                                               | Append two unit tests for the code mapping and the scaffold |

### PR2 files — kipptaf

All paths below are relative to `src/dbt/kipptaf/`.

| File                                                                          | Responsibility                                 |
| ----------------------------------------------------------------------------- | ---------------------------------------------- |
| `models/focus/sources-kippmiami.yml`                                          | Six new source entries with Dagster asset keys |
| `models/focus/intermediate/int_focus__attendance_daily.sql` and five siblings | `union_relations` passthroughs                 |
| `models/students/intermediate/int_students__attendance_daily.sql`             | SIS-neutral union plus all derived calcs       |
| `models/students/intermediate/int_students__ada.sql`                          | SIS-neutral union                              |
| `models/students/intermediate/int_students__attendance_streak.sql`            | SIS-neutral union                              |
| `models/students/intermediate/int_students__calendar_day.sql`                 | SIS-neutral union with crosswalk               |
| `models/students/intermediate/int_students__calendar_week.sql`                | SIS-neutral union with crosswalk               |
| `models/students/intermediate/int_students__calendar_rollup.sql`              | SIS-neutral union with crosswalk               |
| `models/powerschool/intermediate/int_powerschool__ps_adaadm_daily_ctod.sql`   | Reduced to a thin union wrapper                |
| 32 consumer files                                                             | Repointed refs                                 |

---

## PR1 — focus package

### Task 1: `int_focus__attendance_daily`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__attendance_daily.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__attendance_daily.yml`
- Modify: `src/dbt/focus/models/intermediate/unit_tests.yml` (append)

**Interfaces:**

- Consumes: `int_focus__student_enrollment` (`student_number`,
  `network_student_number`, `academic_year`, `schoolid`, `startdate`,
  `exitdate`, `grade_level`), `stg_focus__attendance_calendar` (`school_id`,
  `syear`, `school_date`), `int_focus__attendance_day` (`student_id`,
  `schoolid`, `school_date`, `state_value`, `daily_code`)
- Produces: `int_focus__attendance_daily` with exactly these columns —
  `studentid INT64`, `student_number INT64`, `schoolid INT64`, `entrydate DATE`,
  `calendardate DATE`, `fteid INT64`, `attendance_conversion_id INT64`,
  `grade_level INT64`, `ontrack INT64`, `offtrack INT64`,
  `student_track STRING`, `yearid INT64`, `att_code STRING`,
  `att_code_focus STRING`, `attendancevalue FLOAT64`,
  `potential_attendancevalue FLOAT64`, `membershipvalue FLOAT64`

- [ ] **Step 1: Write the failing unit test**

Append to `src/dbt/focus/models/intermediate/unit_tests.yml`:

```yaml
- name: test_int_focus__attendance_daily_code_mapping_and_scaffold
  model: int_focus__attendance_daily
  description: >-
    Four students on one in-session day inside one stint. Student 84001 is
    absent unexcused (U maps to A), 84002 excused (AE passes through), 84003
    present (null code), and 84004 has no attendance row at all (maps to M and
    counts present, matching PowerSchool). Proves the scaffold emits a row for a
    student Focus never recorded.
  given:
    - input: ref('int_focus__student_enrollment')
      format: sql
      rows: |
        select 84001 as student_number, 1 as network_student_number,
          2026 as academic_year, 58 as schoolid,
          date '2026-08-12' as startdate, date '2027-06-03' as exitdate,
          5 as grade_level
        union all
        select 84002, 2, 2026, 58, date '2026-08-12', date '2027-06-03', 5
        union all
        select 84003, 3, 2026, 58, date '2026-08-12', date '2027-06-03', 5
        union all
        select 84004, 4, 2026, 58, date '2026-08-12', date '2027-06-03', 5
    - input: ref('stg_focus__attendance_calendar')
      format: sql
      rows: |
        select 58 as school_id, 2026 as syear,
          date '2026-08-12' as school_date
    - input: ref('int_focus__attendance_day')
      format: sql
      rows: |
        select 84001 as student_id, 58 as schoolid,
          date '2026-08-12' as school_date,
          cast(0 as numeric) as state_value, 'U' as daily_code
        union all
        select 84002, 58, date '2026-08-12', cast(0 as numeric), 'AE'
        union all
        select 84003, 58, date '2026-08-12', cast(1 as numeric),
          cast(null as string)
  expect:
    format: sql
    rows: |
      select 1 as student_number, 'A' as att_code, 'U' as att_code_focus,
        cast(0.0 as float64) as attendancevalue,
        cast(1.0 as float64) as membershipvalue, 36 as yearid
      union all
      select 2, 'AE', 'AE', cast(0.0 as float64), cast(1.0 as float64), 36
      union all
      select 3, cast(null as string), cast(null as string),
        cast(1.0 as float64), cast(1.0 as float64), 36
      union all
      select 4, 'M', cast(null as string), cast(1.0 as float64),
        cast(1.0 as float64), 36
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run dbt test \
  --select test_int_focus__attendance_daily_code_mapping_and_scaffold \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kippmiami \
  --target dev
```

Expected: FAIL — `Model 'model.focus.int_focus__attendance_daily' not found`.

- [ ] **Step 3: Write the model**

Create `src/dbt/focus/models/intermediate/int_focus__attendance_daily.sql`:

```sql
with
    -- Already deduped to one row per (student_number, academic_year, startdate)
    -- in int_focus__student_enrollment, so the cross with calendar days below
    -- cannot fan out on Focus's duplicate open stints (#4905).
    -- Focus dates a school transfer with the departing stint's exitdate EQUAL to
    -- the arriving stint's startdate, so an inclusive date range counts that day
    -- twice and breaks the (student_number, calendardate) grain. Measured against
    -- prod: 78 stints network-wide are transfer boundaries, while 1,755 stints
    -- legitimately end on an in-session day the student attended -- so a blanket
    -- half-open range would drop 1,755 real attendance days to fix 4 duplicates.
    -- Trim only the transfer day, which assigns it to the ARRIVING school.
    stint_starts as (
        select distinct student_number, academic_year, startdate,
        from {{ ref("int_focus__student_enrollment") }}
    ),

    enrollments as (
        select
            e.student_number,
            e.network_student_number,
            e.academic_year,
            e.schoolid,
            e.startdate,
            e.grade_level,

            if(
                s.startdate is null, e.exitdate, date_sub(e.exitdate, interval 1 day)
            ) as exitdate,
        from {{ ref("int_focus__student_enrollment") }} as e
        -- stint_starts is distinct, so this cannot fan out.
        left join
            stint_starts as s
            on e.student_number = s.student_number
            and e.academic_year = s.academic_year
            and e.exitdate = s.startdate
    ),

    -- Focus's attendance_calendar carries one row per school per day it treats
    -- as in session. There is no insession flag -- presence in the table IS the
    -- flag. minutes is the sentinel 999 on every 2026 row and is not read.
    calendar_days as (
        select school_id, syear, school_date,
        from {{ ref("stg_focus__attendance_calendar") }}
    ),

    -- The membership scaffold. int_focus__attendance_day cannot represent a day
    -- it holds no row for, so absences that were never recorded are invisible
    -- at its grain; crossing enrollment with in-session days is what makes them
    -- representable. Enrollment is the inner side deliberately, which drops the
    -- four misconfigured Focus schools that enrolled nobody. It does NOT drop
    -- school 60 (Applicants), which carries one AY2026 enrollment against a
    -- 212-day holiday-inclusive calendar -- that school has no locations-sheet
    -- row, so the kipptaf crosswalk drops it before anything published reads it.
    -- The calendar misconfiguration is tracked with Ops, not filtered here.
    membership as (
        select
            e.student_number,
            e.network_student_number,
            e.academic_year,
            e.schoolid,
            e.startdate,
            e.grade_level,
            c.school_date,
        from enrollments as e
        inner join
            calendar_days as c
            on e.schoolid = c.school_id
            and e.academic_year = c.syear
            and c.school_date between e.startdate and e.exitdate
    ),

    -- student_id here is the PREFIXED Focus id, which is what
    -- int_focus__student_enrollment exposes as student_number despite the name.
    attendance as (
        select student_id, schoolid, school_date, state_value, daily_code,
        from {{ ref("int_focus__attendance_day") }}
    )

select
    m.schoolid,
    m.grade_level,

    -- Phase 1 left studentid unpopulated for Focus in
    -- int_students__student_enrollment_union, so it stays null here for
    -- consistency. Every downstream join therefore uses student_number.
    cast(null as int64) as studentid,

    m.network_student_number as student_number,
    m.startdate as entrydate,
    m.school_date as calendardate,

    -- PowerSchool-only attendance-conversion machinery with no Focus analogue.
    -- Focus's own fteid is a student FLEID, an unrelated name collision.
    cast(null as int64) as fteid,
    cast(null as int64) as attendance_conversion_id,

    -- PowerSchool calendar tracks. Passthrough columns at kipptaf, never read in
    -- a calc, and Miami's track is already null network-wide.
    cast(null as int64) as ontrack,
    cast(null as int64) as offtrack,
    cast(null as string) as student_track,

    m.academic_year - 1990 as yearid,

    a.daily_code as att_code_focus,

    -- Focus's four day codes conform to the PowerSchool vocabulary with one
    -- rename. AE and AD already match exactly. U must NOT pass through: U means
    -- Unprepared in PowerSchool, so an unmapped U would merge unexcused
    -- absences into an unrelated code. A day with no record maps to M (Missing
    -- Attendance) and counts present, which is what the district ctod does when
    -- no absence row exists.
    case
        when a.student_id is null then 'M'
        when a.daily_code = 'U' then 'A'
        else a.daily_code
    end as att_code,

    -- state_value IS the present/absent classification and is populated on every
    -- Focus row, independent of daily_code. NUMERIC upstream, FLOAT64 here to
    -- match the kipptaf ctod.
    cast(coalesce(a.state_value, 1) as float64) as attendancevalue,

    cast(1 as float64) as potential_attendancevalue,
    cast(1 as float64) as membershipvalue,

from membership as m
left join
    attendance as a
    on m.student_number = a.student_id
    and m.schoolid = a.schoolid
    and m.school_date = a.school_date
```

- [ ] **Step 4: Write the properties file**

Create
`src/dbt/focus/models/intermediate/properties/int_focus__attendance_daily.yml`:

```yaml
models:
  - name: int_focus__attendance_daily
    description: >-
      Focus daily attendance membership — one row per enrolled student per
      in-session calendar day, the analogue of the PowerSchool
      int_powerschool__ps_adaadm_daily_ctod. Built as enrollment crossed with
      in-session calendar days, left-joined to int_focus__attendance_day, so a
      day Focus recorded no row for is still represented. Attendance codes are
      conformed to the PowerSchool vocabulary (U becomes A; AE and AD already
      match; a missing record becomes M and counts present) so network consumers
      need no per-SIS branching. studentid is null because Phase 1 left it
      unpopulated for Focus; every downstream join uses student_number. Emits
      Focus's internal schoolid — kipptaf crosswalks it to the network school
      id. Internal-only — a rpt_ view must sit between this model and any
      external consumer.
    columns:
      - name: student_number
        description: >-
          Network student number, unprefixed. Focus's own student_id carries an
          8400 prefix (Miami-Dade's FLDOE district number) which is stripped
          upstream.
        config:
          meta:
            contains_pii: true
        data_tests:
          - not_null:
              config:
                severity: error
      - name: calendardate
        description: In-session calendar date the membership row represents.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: entrydate
        description: >-
          Start date of the enrollment stint the row belongs to. Focus dates a
          returning student's stint to the real first day of school where
          PowerSchool used a July 1 administrative rollover.
      - name: schoolid
        description: >-
          Focus internal school id (14, 15, 58, 68, 69), not the network school
          number. kipptaf resolves it through the locations crosswalk.
      - name: studentid
        description: >-
          Always null. Focus has no PowerSchool studentid analogue and Phase 1
          left it unpopulated in int_students__student_enrollment_union.
      - name: yearid
        description: Academic year minus 1990, the network-wide formula.
      - name: grade_level
        description: Grade level from the enrollment stint.
      - name: att_code
        description: >-
          Attendance code conformed to the PowerSchool vocabulary — A absent
          undocumented, AE absent excused, AD absent documented, M missing
          record, null present.
      - name: att_code_focus
        description: >-
          Raw Focus daily code before conforming (U, AE, AD, or null), retained
          so the original value is not lost.
      - name: attendancevalue
        description: >-
          1 present, 0 absent, from Focus state_value. A day with no attendance
          record counts present, matching the district ctod.
      - name: potential_attendancevalue
        description: Always 1 — every membership day is potentially attendable.
      - name: membershipvalue
        description: Always 1 — every row is an in-session day within the stint.
      - name: fteid
        description: Always null. PowerSchool attendance-conversion machinery.
      - name: attendance_conversion_id
        description: Always null. PowerSchool attendance-conversion machinery.
      - name: ontrack
        description: Always null. PowerSchool calendar-track machinery.
      - name: offtrack
        description: Always null. PowerSchool calendar-track machinery.
      - name: student_track
        description: Always null. PowerSchool calendar-track machinery.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [student_number, calendardate]
          config:
            severity: error
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run dbt test \
  --select test_int_focus__attendance_daily_code_mapping_and_scaffold \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kippmiami \
  --target dev
```

Expected: PASS.

- [ ] **Step 6: Build the model against real data and check the row counts**

```bash
uv run dbt build --select int_focus__attendance_daily \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kippmiami \
  --defer --state src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS, including the uniqueness test. Then confirm the scaffold
reconciles — query your dev schema (`zz_<your-github-user>_kippmiami_focus`):

```sql
select
  count(*) as scaffold_rows,
  countif(att_code = 'M') as no_record_rows,
  count(distinct student_number) as students,
  count(distinct calendardate) as days
from `teamster-332318.zz_<your-github-user>_kippmiami_focus.int_focus__attendance_daily`
where yearid = 36
```

Expected on 2026-08-19 data: about **307,600 scaffold rows across 212 distinct
days** for roughly 1,628 students, of which about **9,300 rows are elapsed**
(`calendardate <= current_date`).

The model scaffolds the WHOLE school year, not just elapsed days — Focus's
`syear = 2026` calendar is already populated through 2027-06-03, and the
PowerSchool ctod behaves the same way. That is what the `is_realized` flag
downstream exists for. So `att_code = 'M'` is about 97.5% of all rows, because
almost every row is a future day nobody has taken attendance for yet. Judge the
`M` rate on ELAPSED rows only:

```sql
select
  countif(calendardate <= current_date('America/New_York')) as elapsed_rows,
  countif(calendardate <= current_date('America/New_York') and att_code = 'M') as elapsed_m
from `teamster-332318.zz_<your-github-user>_kippmiami_focus.int_focus__attendance_daily`
where yearid = 36
```

Expected: about 9,300 elapsed rows with roughly 130 `M`, so under 2%. An elapsed
`M` rate above 5% means the enrollment or attendance join is wrong, not that
Focus stopped recording.

The 212 distinct days exceed any real school's 182 because Focus school 60
(Applicants) carries one enrollment against a misconfigured 212-day calendar.
That is expected here and is dropped by the kipptaf crosswalk in Task 9.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/focus/models/intermediate/int_focus__attendance_daily.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__attendance_daily.yml \
  src/dbt/focus/models/intermediate/unit_tests.yml </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/focus/models/intermediate/int_focus__attendance_daily.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__attendance_daily.yml \
  src/dbt/focus/models/intermediate/unit_tests.yml && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(focus): add int_focus__attendance_daily membership scaffold

Refs #4924"
```

---

### Task 2: `int_focus__ada`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__ada.sql`
- Create: `src/dbt/focus/models/intermediate/properties/int_focus__ada.yml`

**Interfaces:**

- Consumes: `int_focus__attendance_daily` (`student_number`, `yearid`,
  `membershipvalue`, `attendancevalue`, `calendardate`)
- Produces: `int_focus__ada` with `studentid INT64`, `student_number INT64`,
  `yearid INT64`, `academic_year INT64`, `days_in_membership FLOAT64`,
  `days_present FLOAT64`, `days_absent_unexcused FLOAT64`, `ada FLOAT64`

- [ ] **Step 1: Write the model**

Mirrors the district `int_powerschool__ada` exactly, except it groups by
`student_number` because `studentid` is null on the Focus side.

```sql
select
    yearid,

    yearid + 1990 as academic_year,

    -- Null on the Focus side, projected so the kipptaf union matches the
    -- PowerSchool branch column for column.
    cast(null as int64) as studentid,

    student_number,

    sum(membershipvalue) as days_in_membership,
    sum(attendancevalue) as days_present,
    sum(abs(attendancevalue - 1)) as days_absent_unexcused,

    avg(attendancevalue) as ada,
from {{ ref("int_focus__attendance_daily") }}
where
    membershipvalue = 1 and calendardate <= current_date('{{ var("local_timezone") }}')
group by yearid, student_number
```

- [ ] **Step 2: Write the properties file**

Create `src/dbt/focus/models/intermediate/properties/int_focus__ada.yml`:

```yaml
models:
  - name: int_focus__ada
    description: >-
      Per-student-per-year Focus attendance rollup — the analogue of
      int_powerschool__ada. Counts only realized membership days
      (membershipvalue 1 and calendardate on or before today), so a future
      year-end day cannot dilute the average. Grouped by student_number rather
      than studentid because Focus has no studentid. Internal-only — a rpt_ view
      must sit between this model and any external consumer.
    columns:
      - name: student_number
        description: Network student number, unprefixed.
        config:
          meta:
            contains_pii: true
        data_tests:
          - not_null:
              config:
                severity: error
      - name: studentid
        description: Always null. Focus has no PowerSchool studentid analogue.
      - name: yearid
        description: Academic year minus 1990.
      - name: academic_year
        description: Academic year start year (2026 = 2026-27).
      - name: days_in_membership
        description: Realized in-session days the student was enrolled for.
      - name: days_present
        description: Realized membership days the student was present for.
      - name: days_absent_unexcused
        description: >-
          Realized membership days the student was absent for. Named for parity
          with int_powerschool__ada; Focus does not split excused from unexcused
          at this grain.
      - name: ada
        description: Average daily attendance across realized membership days.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [student_number, yearid]
          config:
            severity: error
```

- [ ] **Step 2b: Build and verify**

```bash
uv run dbt build --select int_focus__ada \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kippmiami \
  --defer --state src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS. Then confirm ADA is plausible — every value between 0 and 1, and
the network mean near 0.95:

```sql
select
  count(*) as students, min(ada) as min_ada, max(ada) as max_ada,
  avg(ada) as mean_ada
from `teamster-332318.zz_<your-github-user>_kippmiami_focus.int_focus__ada`
where yearid = 36
```

Expected: about 1,559 students, `min_ada` at or above 0, `max_ada` exactly 1,
`mean_ada` between 0.90 and 1.00. A `max_ada` above 1 means the scaffold
double-counted a student-day.

- [ ] **Step 3: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/focus/models/intermediate/int_focus__ada.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__ada.yml </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/focus/models/intermediate/int_focus__ada.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__ada.yml && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(focus): add int_focus__ada rollup

Refs #4924"
```

---

### Task 3: `int_focus__attendance_streak`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__attendance_streak.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__attendance_streak.yml`

**Interfaces:**

- Consumes: `int_focus__attendance_daily` (`student_number`, `yearid`,
  `calendardate`, `attendancevalue`, `att_code`, `membershipvalue`)
- Produces: `int_focus__attendance_streak` with `studentid INT64`,
  `student_number INT64`, `yearid INT64`, `att_code STRING`, `streak_id STRING`,
  `streak_start_date DATE`, `streak_end_date DATE`,
  `streak_length_membership INT64`, `streak_length_calendar INT64`

- [ ] **Step 1: Write the model**

Mirrors the district `int_powerschool__attendance_streak`, with `student_number`
substituted for `studentid` in every partition and every hash.

```sql
with
    -- studentid is null on the Focus side, and generate_surrogate_key maps null
    -- to a single constant -- hashing it would collapse every Focus student into
    -- one streak per year and code. student_number is the key throughout.
    att_mem as (
        select
            student_number,
            yearid,
            calendardate,
            attendancevalue,

            '{{ project_name }}' as project_name,

            coalesce(att_code, 'P') as att_code,

            row_number() over (
                partition by student_number, yearid order by calendardate asc
            ) as membership_day_number,

            row_number() over (
                partition by student_number, yearid, cast(attendancevalue as string)
                order by calendardate asc
            ) as rn_student_year_attendancevalue,

            row_number() over (
                partition by student_number, yearid, att_code
                order by calendardate asc
            ) as rn_student_year_code,
        from {{ ref("int_focus__attendance_daily") }}
        where membershipvalue = 1
    ),

    streaks_long as (
        select
            student_number,
            yearid,
            calendardate,
            att_code,
            attendancevalue,
            membership_day_number,
            rn_student_year_code,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "'code'",
                        "project_name",
                        "student_number",
                        "yearid",
                        "att_code",
                        "(membership_day_number - rn_student_year_code)",
                    ]
                )
            }} as code_streak_id,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "'att'",
                        "project_name",
                        "student_number",
                        "yearid",
                        "attendancevalue",
                        "(membership_day_number - rn_student_year_attendancevalue)",
                    ]
                )
            }} as att_streak_id,
        from att_mem
    ),

    streaks_agg as (
        select
            student_number,
            yearid,
            att_code,
            code_streak_id as streak_id,

            min(calendardate) as streak_start_date,
            max(calendardate) as streak_end_date,
            count(calendardate) as streak_length_membership,
        from streaks_long
        group by student_number, yearid, att_code, code_streak_id

        union all

        select
            student_number,
            yearid,

            cast(attendancevalue as string) as att_code,

            att_streak_id as streak_id,

            min(calendardate) as streak_start_date,
            max(calendardate) as streak_end_date,
            count(calendardate) as streak_length_membership,
        from streaks_long
        group by student_number, yearid, attendancevalue, att_streak_id
    )

select
    *,

    -- Projected null so the kipptaf union matches the PowerSchool branch column
    -- for column.
    cast(null as int64) as studentid,

    date_diff(streak_end_date, streak_start_date, day) + 1 as streak_length_calendar,
from streaks_agg
```

- [ ] **Step 2: Write the properties file**

Create
`src/dbt/focus/models/intermediate/properties/int_focus__attendance_streak.yml`:

```yaml
models:
  - name: int_focus__attendance_streak
    description: >-
      Consecutive-day Focus attendance streaks — the analogue of
      int_powerschool__attendance_streak. Two streak families in one relation:
      by attendance code (att_code holds the code) and by attendance value
      (att_code holds the stringified 0 or 1). Keyed on student_number, not
      studentid, because studentid is null on the Focus side and hashing a null
      would collapse every student into one streak. Internal-only — a rpt_ view
      must sit between this model and any external consumer.
    columns:
      - name: streak_id
        description: >-
          Surrogate key for the streak, hashed from the streak family, project
          name, student_number, yearid, the code or value, and the gap between
          the membership-day number and the per-code row number.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: student_number
        description: Network student number, unprefixed.
        config:
          meta:
            contains_pii: true
        data_tests:
          - not_null:
              config:
                severity: error
      - name: studentid
        description: Always null. Focus has no PowerSchool studentid analogue.
      - name: yearid
        description: Academic year minus 1990.
      - name: att_code
        description: >-
          The conformed attendance code for a code streak (P for present), or
          the stringified attendance value for a value streak.
      - name: streak_start_date
        description: First membership day in the streak.
      - name: streak_end_date
        description: Last membership day in the streak.
      - name: streak_length_membership
        description: Count of membership days in the streak.
      - name: streak_length_calendar
        description: >-
          Calendar days spanned by the streak, inclusive. Larger than
          streak_length_membership when the streak spans a weekend or break.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [streak_id, att_code]
          config:
            severity: error
```

- [ ] **Step 3: Build and verify**

```bash
uv run dbt build --select int_focus__attendance_streak \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kippmiami \
  --defer --state src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS. Then confirm streaks did not collapse — the null-studentid trap
this model exists to avoid:

```sql
select
  count(*) as streak_rows,
  count(distinct streak_id) as distinct_streaks,
  count(distinct student_number) as students,
  max(streak_length_membership) as longest
from `teamster-332318.zz_<your-github-user>_kippmiami_focus.int_focus__attendance_streak`
where yearid = 36
```

Expected: `students` about 1,559, and `longest` at most 6 (only 6 in-session
days have elapsed). A `longest` in the thousands means a hash collapsed and the
model is hashing a null.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/focus/models/intermediate/int_focus__attendance_streak.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__attendance_streak.yml </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/focus/models/intermediate/int_focus__attendance_streak.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__attendance_streak.yml && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(focus): add int_focus__attendance_streak

Refs #4924"
```

---

### Task 4: `int_focus__calendar_day`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__calendar_day.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__calendar_day.yml`

**Interfaces:**

- Consumes: `stg_focus__attendance_calendar` (`school_id`, `syear`,
  `school_date`)
- Produces: `int_focus__calendar_day` with `schoolid INT64`, `date_value DATE`,
  `insession INT64`, `membershipvalue FLOAT64`, `week_start_date DATE`,
  `week_end_date DATE`, `yearid INT64`

- [ ] **Step 1: Write the model**

```sql
select
    school_id as schoolid,
    school_date as date_value,

    syear - 1990 as yearid,

    -- Focus has no insession flag. A row in attendance_calendar IS an in-session
    -- day, and Focus carries no membership-value concept, so both are constants.
    -- Five schools (2 closed, 3 non-instructional) carry unfiltered 212-day
    -- calendars including holidays; that is a Focus configuration problem handed
    -- to Ops, not something filtered here. The warn test in the kipptaf union
    -- surfaces the rows.
    1 as insession,
    cast(1 as float64) as membershipvalue,

    -- Matches stg_powerschool__calendar_day: week_start_date is the Sunday,
    -- week_end_date the following Saturday.
    date_trunc(school_date, week) as week_start_date,
    date_add(date_trunc(school_date, week), interval 6 day) as week_end_date,

from {{ ref("stg_focus__attendance_calendar") }}
```

- [ ] **Step 2: Write the properties file**

Create
`src/dbt/focus/models/intermediate/properties/int_focus__calendar_day.yml`:

```yaml
models:
  - name: int_focus__calendar_day
    description: >-
      Focus in-session calendar days — the analogue of
      stg_powerschool__calendar_day for the columns network consumers read.
      Presence of a row in Focus's attendance_calendar is itself the in-session
      flag, so insession and membershipvalue are constants rather than sourced
      values. Emits Focus's internal schoolid; kipptaf crosswalks it. Five Focus
      schools carry unfiltered 212-day calendars that include holidays — a Focus
      configuration problem tracked with Ops, deliberately not filtered here.
      Internal-only — a rpt_ view must sit between this model and any external
      consumer.
    columns:
      - name: schoolid
        description: >-
          Focus internal school id, not the network school number. kipptaf
          resolves it through the locations crosswalk.
      - name: date_value
        description: The in-session calendar date.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: yearid
        description: Academic year minus 1990.
      - name: insession
        description: Always 1 — a row exists only for an in-session day.
      - name: membershipvalue
        description: >-
          Always 1. Focus has no membership-value concept; PowerSchool uses it
          to mark partial-membership days.
      - name: week_start_date
        description: Sunday of the week the date falls in.
      - name: week_end_date
        description: Saturday of the week the date falls in.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [schoolid, date_value]
          config:
            severity: error
```

- [ ] **Step 3: Build and verify**

```bash
uv run dbt build --select int_focus__calendar_day \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kippmiami \
  --defer --state src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS. Then confirm the known-bad calendars are visible rather than
silently absent:

```sql
select schoolid, count(*) as n_days
from `teamster-332318.zz_<your-github-user>_kippmiami_focus.int_focus__calendar_day`
where yearid = 36
group by schoolid
order by schoolid
```

Expected: schools 14, 15, 58, 68, 69 at 182 days, and schools 60, 62, 70, 71, 72
at 212. The 212s are the Ops item and must still appear here — this model does
not filter them.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/focus/models/intermediate/int_focus__calendar_day.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__calendar_day.yml </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/focus/models/intermediate/int_focus__calendar_day.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__calendar_day.yml && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(focus): add int_focus__calendar_day

Refs #4924"
```

---

### Task 5: `int_focus__calendar_week`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__calendar_week.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__calendar_week.yml`

**Interfaces:**

- Consumes: `int_focus__calendar_day` (`schoolid`, `date_value`, `yearid`,
  `week_start_date`, `week_end_date`), `stg_focus__marking_periods`
  (`school_id`, `syear`, `short_name`, `type`, `start_date`, `end_date`,
  `quarter_semester`), `int_focus__schools` (`id`, `school_level`)
- Produces: `int_focus__calendar_week` with `schoolid INT64`,
  `week_start_date DATE`, `week_end_date DATE`, `school_level STRING`,
  `yearid INT64`, `academic_year INT64`, `week_start_monday DATE`,
  `week_end_sunday DATE`, `school_week_start_date DATE`,
  `school_week_end_date DATE`, `date_count INT64`, `semester STRING`,
  `quarter STRING`, `first_day_school_year DATE`,
  `last_week_start_school_year DATE`, `last_day_school_year DATE`,
  `school_week_start_date_lead DATE`, `week_number_academic_year INT64`,
  `week_number_quarter INT64`, `is_current_week_mon_sun BOOL`

- [ ] **Step 1: Write the model**

Mirrors the district `int_powerschool__calendar_week` column for column. Focus
has no `cycle_day` or `bell_schedule` tables — those joins in the PowerSchool
version only assert a valid schedule exists, and Focus's calendar rows carry no
equivalent, so they are dropped rather than faked.

```sql
with
    week_rollup as (
        select
            cd.schoolid,
            cd.week_start_date,
            cd.week_end_date,
            cd.yearid,

            sch.school_level,

            cd.yearid + 1990 as academic_year,

            date_add(cd.week_start_date, interval 1 day) as week_start_monday,
            date_add(cd.week_end_date, interval 1 day) as week_end_sunday,

            min(cd.date_value) as school_week_start_date,
            max(cd.date_value) as school_week_end_date,
            count(cd.date_value) as date_count,

            max(mp.quarter_semester) as semester,
            max(mp.short_name) as `quarter`,
        from {{ ref("int_focus__calendar_day") }} as cd
        inner join {{ ref("int_focus__schools") }} as sch on cd.schoolid = sch.id
        -- Quarter marking periods only, matching the PowerSchool version's
        -- portion = 4 filter on termbins.
        inner join
            {{ ref("stg_focus__marking_periods") }} as mp
            on cd.schoolid = mp.school_id
            and cd.yearid + 1990 = mp.syear
            and cd.date_value between mp.start_date and mp.end_date
            and mp.type = 'quarter'
        group by
            cd.schoolid,
            cd.week_start_date,
            cd.week_end_date,
            cd.yearid,
            sch.school_level
    ),

    window_calcs as (
        select
            *,

            min(week_start_monday) over (
                partition by schoolid, yearid
            ) as first_day_school_year,
            max(week_start_monday) over (
                partition by schoolid, yearid
            ) as last_week_start_school_year,

            max(school_week_end_date) over (
                partition by schoolid, yearid
            ) as last_day_school_year,

            lead(school_week_start_date) over (
                partition by schoolid, yearid order by week_start_date asc
            ) as school_week_start_date_lead,

            row_number() over (
                partition by schoolid, yearid order by week_start_date asc
            ) as week_number_academic_year,
            row_number() over (
                partition by schoolid, yearid, `quarter` order by week_start_date asc
            ) as week_number_quarter,

        from week_rollup
    )

select
    *,

    case
        when
            academic_year = {{ var("current_academic_year") }}
            and current_date('{{ var("local_timezone") }}')
            between week_start_monday and week_end_sunday
        then true
        when
            academic_year = {{ var("current_academic_year") }}
            and current_date('{{ var("local_timezone") }}')
            > date_add(last_week_start_school_year, interval 6 day)
            and week_start_monday = last_week_start_school_year
        then true
        else false
    end as is_current_week_mon_sun,

from window_calcs
```

- [ ] **Step 2: Write the properties file**

Create
`src/dbt/focus/models/intermediate/properties/int_focus__calendar_week.yml`:

```yaml
models:
  - name: int_focus__calendar_week
    description: >-
      Focus school weeks — the analogue of int_powerschool__calendar_week, one
      row per school per week that contains at least one in-session day inside a
      quarter marking period. Quarter and semester come from
      stg_focus__marking_periods rather than PowerSchool termbins. Focus has no
      cycle_day or bell_schedule analogue, so those PowerSchool joins are
      dropped rather than faked; they only asserted a valid schedule existed.
      Emits Focus's internal schoolid; kipptaf crosswalks it. Internal-only — a
      rpt_ view must sit between this model and any external consumer.
    columns:
      - name: schoolid
        description: >-
          Focus internal school id, not the network school number. kipptaf
          resolves it through the locations crosswalk.
      - name: week_start_date
        description: Sunday of the week.
      - name: week_end_date
        description: Saturday of the week.
      - name: week_start_monday
        description: Monday of the week, the network-standard week anchor.
      - name: week_end_sunday
        description: Sunday following the week.
      - name: school_level
        description: ES, MS, or HS from int_focus__schools.
      - name: yearid
        description: Academic year minus 1990.
      - name: academic_year
        description: Academic year start year (2026 = 2026-27).
      - name: school_week_start_date
        description: First in-session day in the week.
      - name: school_week_end_date
        description: Last in-session day in the week.
      - name: date_count
        description: Count of in-session days in the week.
      - name: semester
        description: S1 or S2, derived from the quarter marking period.
      - name: quarter
        description: Quarter short name (Q1 through Q4).
      - name: first_day_school_year
        description: Monday of the school year's first week, per school.
      - name: last_week_start_school_year
        description: Monday of the school year's last week, per school.
      - name: last_day_school_year
        description: Last in-session day of the school year, per school.
      - name: school_week_start_date_lead
        description: First in-session day of the following week.
      - name: week_number_academic_year
        description: Sequential week number within the school year.
      - name: week_number_quarter
        description: Sequential week number within the quarter.
      - name: is_current_week_mon_sun
        description: >-
          True for the current week in the current academic year, and for the
          final week once the year has ended.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [schoolid, yearid, week_start_date]
          config:
            severity: error
```

- [ ] **Step 3: Build and verify**

```bash
uv run dbt build --select int_focus__calendar_week \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kippmiami \
  --defer --state src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS. Then confirm the week grain and that quarters resolved:

```sql
select
  schoolid,
  count(*) as n_weeks,
  countif(`quarter` is null) as n_null_quarter,
  sum(date_count) as total_days
from `teamster-332318.zz_<your-github-user>_kippmiami_focus.int_focus__calendar_week`
where yearid = 36
group by schoolid
order by schoolid
```

Expected: `n_null_quarter` is 0 on every row — a null quarter means the marking
period join missed. The five real schools should show roughly 38 to 40 weeks and
`total_days` at or below 182.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/focus/models/intermediate/int_focus__calendar_week.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__calendar_week.yml </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/focus/models/intermediate/int_focus__calendar_week.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__calendar_week.yml && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(focus): add int_focus__calendar_week

Refs #4924"
```

---

### Task 6: `int_focus__calendar_rollup`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__calendar_rollup.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__calendar_rollup.yml`

**Interfaces:**

- Consumes: `int_focus__calendar_day` (`schoolid`, `yearid`, `date_value`)
- Produces: `int_focus__calendar_rollup` with `schoolid INT64`, `yearid INT64`,
  `track STRING`, `min_calendardate DATE`, `max_calendardate DATE`,
  `days_total INT64`, `days_remaining INT64`

- [ ] **Step 1: Write the model**

```sql
select
    schoolid,
    yearid,

    -- PowerSchool derives one row per calendar track (A through F) by unpivoting
    -- the calendar_day track columns. Focus has no track concept, and Miami's
    -- track is already null on every row of int_extracts__student_enrollments,
    -- so a fabricated 'A' would be no more joinable than null. One row per
    -- school-year with a null track, and the ops dashboard join is made
    -- null-safe in the kipptaf task that repoints it.
    cast(null as string) as track,

    min(date_value) as min_calendardate,
    max(date_value) as max_calendardate,
    count(date_value) as days_total,
    sum(
        if(date_value > current_date('{{ var("local_timezone") }}'), 1, 0)
    ) as days_remaining,
from {{ ref("int_focus__calendar_day") }}
group by schoolid, yearid
```

- [ ] **Step 2: Write the properties file**

Create
`src/dbt/focus/models/intermediate/properties/int_focus__calendar_rollup.yml`:

```yaml
models:
  - name: int_focus__calendar_rollup
    description: >-
      Per-school-per-year Focus instructional day totals — the analogue of
      int_powerschool__calendar_rollup. PowerSchool emits one row per calendar
      track by unpivoting its calendar_day track columns; Focus has no track
      concept and Miami's track is already null throughout the network layer, so
      this emits one row per school-year with a null track. Emits Focus's
      internal schoolid; kipptaf crosswalks it. Internal-only — a rpt_ view must
      sit between this model and any external consumer.
    columns:
      - name: schoolid
        description: >-
          Focus internal school id, not the network school number. kipptaf
          resolves it through the locations crosswalk.
      - name: yearid
        description: Academic year minus 1990.
      - name: track
        description: >-
          Always null. Focus has no calendar-track concept and Miami's track is
          null on every network enrollment row.
      - name: min_calendardate
        description: First in-session day of the school year.
      - name: max_calendardate
        description: Last in-session day of the school year.
      - name: days_total
        description: Total in-session days in the school year.
      - name: days_remaining
        description: In-session days still in the future as of today.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [schoolid, yearid]
          config:
            severity: error
```

- [ ] **Step 3: Build and verify**

```bash
uv run dbt build --select int_focus__calendar_rollup \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kippmiami \
  --defer --state src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS. Then confirm the totals:

```sql
select schoolid, days_total, days_remaining, min_calendardate, max_calendardate
from `teamster-332318.zz_<your-github-user>_kippmiami_focus.int_focus__calendar_rollup`
where yearid = 36
order by schoolid
```

Expected: the five real schools at `days_total` 182, `days_remaining` 176, and
`min_calendardate` 2026-08-12.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/focus/models/intermediate/int_focus__calendar_rollup.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__calendar_rollup.yml </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/focus/models/intermediate/int_focus__calendar_rollup.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__calendar_rollup.yml && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(focus): add int_focus__calendar_rollup

Refs #4924"
```

---

### Task 7: Ship PR1 and wait for prod materialization

**Files:** none — this is a gate.

- [ ] **Step 1: Build the whole new subgraph together**

```bash
uv run dbt build --select int_focus__attendance_daily+ int_focus__calendar_day+ \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kippmiami \
  --defer --state src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS on all six models and every data test.

- [ ] **Step 2: Lint everything the PR touches**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C . diff --name-only origin/main...HEAD | while read -r f; do [ -f "$f" ] && printf '%s ' "$f"; done) </dev/null
```

Expected: `No issues`.

- [ ] **Step 3: Push and open PR1**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer push
```

Open the PR with `.github/pull_request_template.md` as the body. Body must state
plainly that **dbt Cloud CI does not validate this PR** — CI builds `kipptaf`
alone, so a package-only PR selects zero modified models and goes green
trivially. The local build in Step 1 is the validation. Include `Refs #4924`.

- [ ] **Step 4: After merge, confirm prod materialization**

All six models must exist and be populated in `kippmiami_focus` before PR2 can
read them. Check with `mcp__dagster__get_asset_materializations`, or:

```sql
select table_name, row_count
from `teamster-332318.kippmiami_focus.__TABLES__`
where table_name in (
  'int_focus__attendance_daily', 'int_focus__ada',
  'int_focus__attendance_streak', 'int_focus__calendar_day',
  'int_focus__calendar_week', 'int_focus__calendar_rollup'
)
```

Expected: six rows. `__TABLES__.row_count` lags, so confirm population with
`count(*)` on `int_focus__attendance_daily` rather than trusting it. **Do not
start PR2 until all six are populated in prod.**

---

## PR2 — kipptaf

### Task 8: Source declarations and passthrough wrappers

**Files:**

- Modify: `src/dbt/kipptaf/models/focus/sources-kippmiami.yml`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__attendance_daily.sql`
- Create: `src/dbt/kipptaf/models/focus/intermediate/int_focus__ada.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__attendance_streak.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__calendar_day.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__calendar_week.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__calendar_rollup.sql`

**Interfaces:**

- Consumes: the six prod-materialized `kippmiami_focus` relations from PR1
- Produces: six kipptaf models of the same names, each adding
  `_dbt_source_project STRING`

- [ ] **Step 1: Add the six source entries**

Append to the `tables:` list in
`src/dbt/kipptaf/models/focus/sources-kippmiami.yml`, following the existing
entry shape exactly:

```yaml
- name: int_focus__attendance_daily
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - int_focus__attendance_daily
- name: int_focus__ada
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - int_focus__ada
- name: int_focus__attendance_streak
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - int_focus__attendance_streak
- name: int_focus__calendar_day
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - int_focus__calendar_day
- name: int_focus__calendar_week
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - int_focus__calendar_week
- name: int_focus__calendar_rollup
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - int_focus__calendar_rollup
```

- [ ] **Step 2: Create the six passthrough wrappers**

Every source added to a `sources-kipp*.yml` needs a matching `union_relations`
passthrough, and consumers read the wrapper, never the source. Each of the six
files is identical apart from the model name. For
`int_focus__attendance_daily.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__attendance_daily"),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

Repeat for `int_focus__ada.sql`, `int_focus__attendance_streak.sql`,
`int_focus__calendar_day.sql`, `int_focus__calendar_week.sql`, and
`int_focus__calendar_rollup.sql`, substituting the model name in both the
filename and the `source()` call.

- [ ] **Step 3: Refresh the staging copies**

**This step is the user's to run** — it recreates shared `zz_stg_*` tables and
needs direct authorization. Without it, CI reads a stale
`zz_stg_kippmiami_focus` that lacks the six new relations and fails
deterministically.

```bash
uv run dbt clone --select int_focus__attendance_daily int_focus__ada \
  int_focus__attendance_streak int_focus__calendar_week \
  int_focus__calendar_rollup int_focus__calendar_day \
  --target staging --state src/dbt/kippmiami/target/prod \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kippmiami
```

- [ ] **Step 4: Verify the wrappers parse and resolve**

```bash
uv run dbt build --empty --select int_focus__attendance_daily int_focus__ada \
  int_focus__attendance_streak int_focus__calendar_day \
  int_focus__calendar_week int_focus__calendar_rollup \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kipptaf \
  --defer --state src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS on all six. `--empty` proves column resolution only, not values.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/focus/sources-kippmiami.yml \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__attendance_daily.sql \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__ada.sql \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__attendance_streak.sql \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__calendar_day.sql \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__calendar_week.sql \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__calendar_rollup.sql </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/kipptaf/models/focus/sources-kippmiami.yml \
  src/dbt/kipptaf/models/focus/intermediate/ && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(kipptaf): declare and wrap the Focus attendance sources

Refs #4924"
```

---

### Task 9: `int_students__calendar_day` and repoint `dim_school_calendars`

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__calendar_day.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__calendar_day.yml`
- Create:
  `src/dbt/kipptaf/tests/int_students__calendar_day__zero_enrollment_in_session_days.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_school_calendars.sql:6`

**Interfaces:**

- Consumes: `stg_powerschool__calendar_day`, `int_focus__calendar_day` (kipptaf
  wrapper), `int_focus__schools`, `stg_google_sheets__people__locations`
- Produces: `int_students__calendar_day` with `schoolid INT64` (network school
  number), `date_value DATE`, `insession INT64`, `membershipvalue FLOAT64`,
  `week_start_date DATE`, `week_end_date DATE`, `yearid INT64`,
  `_dbt_source_relation STRING`, `_dbt_source_project STRING`

- [ ] **Step 1: Write the model**

The crosswalk CTE here is the pattern every remaining `int_students__*` task
reuses. It resolves Focus's internal school id to the network school number
through the Florida code, matching the `focus_schools` CTE in
`int_students__terms`.

```sql
with
    -- Focus's school_id is its internal id (14, 15, 58...), not the network
    -- school number, and it differs from the "school_number" the focus package
    -- exposes (a Florida code like 2332A). Resolve through both hops. The inner
    -- join is also the filter that drops Focus's three non-instructional schools
    -- (Applicants, Virtual Franchise, ZZ Course History), which have no
    -- locations row.
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    focus_years as (
        select distinct yearid, from {{ ref("int_focus__calendar_day") }}
    ),

    -- The frozen PowerSchool archive keeps serving Miami for every year Focus
    -- does not cover. Scoping by year rather than by project is what preserves
    -- Miami AY2020 through AY2025.
    powerschool_conformed as (
        select
            cd._dbt_source_relation,
            cd._dbt_source_project,
            cd.schoolid,
            cd.insession,
            cd.membershipvalue,
            cd.week_start_date,
            cd.week_end_date,
            cd.date_value,

            t.yearid,
        from {{ ref("stg_powerschool__calendar_day") }} as cd
        inner join
            {{ ref("stg_powerschool__terms") }} as t
            on cd.schoolid = t.schoolid
            and cd.date_value between t.firstday and t.lastday
            and cd._dbt_source_project = t._dbt_source_project
            and t.isyearrec = 1
        where
            not (
                cd._dbt_source_project = 'kippmiami'
                and t.yearid in (select yearid from focus_years)
            )
    ),

    focus_conformed as (
        select
            cd._dbt_source_relation,
            cd._dbt_source_project,
            cd.insession,
            cd.membershipvalue,
            cd.week_start_date,
            cd.week_end_date,
            cd.date_value,
            cd.yearid,

            fs.schoolid,
        from {{ ref("int_focus__calendar_day") }} as cd
        inner join focus_schools as fs on cd.schoolid = fs.focus_school_id
    )

-- `full union all corresponding` matches columns by NAME. A plain `union all`
-- matches by POSITION, and the two CTEs above list schoolid in different
-- positions, which would silently align schoolid with insession.
select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
```

- [ ] **Step 2: Write the properties file with the Ops warn test**

Create
`src/dbt/kipptaf/models/students/intermediate/properties/int_students__calendar_day.yml`:

```yaml
models:
  - name: int_students__calendar_day
    description: >-
      SIS-neutral in-session school calendar days across the network. The
      PowerSchool branch is year-scoped so the frozen Miami archive keeps
      serving the years Focus does not cover; Focus serves AY2026 forward.
      Focus's internal school id is crosswalked to the network school number
      here, because the crosswalk sheet is a kipptaf model the focus package
      cannot reach.
    columns:
      - name: schoolid
        description: Network school number.
      - name: date_value
        description: The in-session calendar date.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: yearid
        description: Academic year minus 1990.
      - name: insession
        description: 1 when the day is in session.
      - name: membershipvalue
        description: Membership weight for the day; greater than 0 counts.
      - name: week_start_date
        description: Sunday of the week the date falls in.
      - name: week_end_date
        description: Saturday of the week the date falls in.
      - name: _dbt_source_project
        description: Originating district project.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [schoolid, date_value, _dbt_source_project]
          config:
            severity: error
      # Surfaces the Focus calendar misconfiguration handed to Ops: five Focus
      # schools carry unfiltered 212-day calendars including holidays, and the
      # two closed ones map to live location keys. Warn, not error -- the fix is
      # in Focus, not here. Deliberately NOT a holiday-date test: Thanksgiving is
      # the fourth Thursday, so a hardcoded 11-26 would catch AY2026 only. An
      # in-session day at a school that enrolled nobody that year is
      # date-independent and catches the whole class.
      - zero_enrollment_in_session_days:
          config:
            severity: warn
```

- [ ] **Step 2b: Write the singular test the properties file references**

Create
`src/dbt/kipptaf/tests/int_students__calendar_day__zero_enrollment_in_session_days.sql`
and register it in `src/dbt/kipptaf/tests/properties.yml`, following the shape
of the entries already there. A generic `dbt_utils.expression_is_true` cannot
express this — it needs a join to enrollment.

```sql
-- Focus in-session days at a school that enrolled nobody that year. Five Focus
-- schools carry unfiltered 212-day calendars including holidays and breaks; two
-- of them are closed but still map to live network location keys, so their days
-- reach dim_school_calendars. The fix belongs in Focus configuration, so this
-- warns rather than errors -- it makes the rows visible without hiding them.
select cd.schoolid, cd.yearid, count(*) as n_days,
from {{ ref("int_students__calendar_day") }} as cd
left join
    {{ ref("int_students__student_enrollment_union") }} as e
    on cd.schoolid = e.schoolid
    and cd.yearid = e.academic_year - 1990
    and cd._dbt_source_project = e._dbt_source_project
where cd._dbt_source_project = 'kippmiami' and e.schoolid is null
group by cd.schoolid, cd.yearid
```

Expected when it runs: WARN naming Focus schools 71 and 72, the two closed
schools, for `yearid` 36. Schools 60, 62, and 70 never reach this model — they
have no locations-sheet row, so the crosswalk drops them.

- [ ] **Step 3: Repoint `dim_school_calendars`**

In `src/dbt/kipptaf/models/marts/dimensions/dim_school_calendars.sql`, change
line 6 only:

```sql
from {{ ref("int_students__calendar_day") }} as cd
```

Leave every other line unchanged. The join already reads `cd.schoolid` against
`sch.school_number`, which the new model emits as the network school number.

- [ ] **Step 4: Build and verify NJ parity plus Miami presence**

```bash
uv run dbt build --select int_students__calendar_day dim_school_calendars \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kipptaf \
  --defer --state src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS, with the Ops warn test WARNING on the two closed schools. A warn
here is the expected outcome, not a failure.

Then compare NJ against prod. NJ counts must be identical:

```sql
select
  'dev' as src, _dbt_source_project, count(*) as n,
  count(distinct format('%T|%T', schoolid, date_value)) as n_keys
from `teamster-332318.zz_<your-github-user>_kipptaf_students.int_students__calendar_day`
where _dbt_source_project != 'kippmiami'
group by 1, 2
union all
select
  'prod', _dbt_source_project, count(*),
  count(distinct format('%T|%T', schoolid, date_value))
from `teamster-332318.kipptaf_powerschool.stg_powerschool__calendar_day` as cd
inner join `teamster-332318.kipptaf_powerschool.stg_powerschool__terms` as t
  on cd.schoolid = t.schoolid
  and cd.date_value between t.firstday and t.lastday
  and cd._dbt_source_project = t._dbt_source_project
  and t.isyearrec = 1
where cd._dbt_source_project != 'kippmiami'
group by 1, 2
order by 2, 1
```

Expected: `n` and `n_keys` match between `dev` and `prod` for kippnewark,
kippcamden, and kipppaterson. Any difference means the year-scoping predicate is
wrong.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/students/intermediate/int_students__calendar_day.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__calendar_day.yml \
  src/dbt/kipptaf/tests/int_students__calendar_day__zero_enrollment_in_session_days.sql \
  src/dbt/kipptaf/tests/properties.yml \
  src/dbt/kipptaf/models/marts/dimensions/dim_school_calendars.sql </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/kipptaf/models/students/intermediate/int_students__calendar_day.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__calendar_day.yml \
  src/dbt/kipptaf/tests/int_students__calendar_day__zero_enrollment_in_session_days.sql \
  src/dbt/kipptaf/tests/properties.yml \
  src/dbt/kipptaf/models/marts/dimensions/dim_school_calendars.sql && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(kipptaf): add int_students__calendar_day and repoint dim_school_calendars

Refs #4924"
```

---

### Task 10: `int_students__calendar_week` and 17 repoints

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__calendar_week.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__calendar_week.yml`
- Modify: 15 consumer files, 17 refs total

**Interfaces:**

- Consumes: `int_powerschool__calendar_week`, `int_focus__calendar_week`
  (kipptaf wrapper), `int_focus__schools`,
  `stg_google_sheets__people__locations`
- Produces: `int_students__calendar_week` with the same columns as
  `int_powerschool__calendar_week` plus `_dbt_source_project`, and `schoolid` as
  the network school number

- [ ] **Step 1: Write the model**

```sql
with
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    focus_years as (
        select distinct yearid, from {{ ref("int_focus__calendar_week") }}
    ),

    powerschool_conformed as (
        select *,
        from {{ ref("int_powerschool__calendar_week") }}
        where
            not (
                _dbt_source_project = 'kippmiami'
                and yearid in (select yearid from focus_years)
            )
    ),

    focus_conformed as (
        select
            cw.* except (schoolid),

            fs.schoolid,

            initcap(
                regexp_extract(cw._dbt_source_relation, r'kipp(\w+)_')
            ) as region,
        from {{ ref("int_focus__calendar_week") }} as cw
        inner join focus_schools as fs on cw.schoolid = fs.focus_school_id
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
```

- [ ] **Step 2: Write the properties file**

Create
`src/dbt/kipptaf/models/students/intermediate/properties/int_students__calendar_week.yml`:

```yaml
models:
  - name: int_students__calendar_week
    description: >-
      SIS-neutral school weeks across the network — the successor to
      int_powerschool__calendar_week, which stays a pure PowerSchool union. The
      PowerSchool branch is year-scoped so the frozen Miami archive keeps
      serving the years Focus does not cover. Focus's internal school id is
      crosswalked to the network school number here.
    columns:
      - name: schoolid
        description: Network school number.
      - name: yearid
        description: Academic year minus 1990.
      - name: academic_year
        description: Academic year start year (2026 = 2026-27).
      - name: week_start_monday
        description: Monday of the week, the network-standard week anchor.
      - name: week_end_sunday
        description: Sunday following the week.
      - name: region
        description: Region name derived from the source relation.
      - name: _dbt_source_project
        description: Originating district project.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              [schoolid, yearid, week_start_date, _dbt_source_project]
          config:
            severity: error
```

- [ ] **Step 3: Repoint all 17 refs**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
grep -rl 'ref("int_powerschool__calendar_week")' --include='*.sql' src/dbt/kipptaf/models/ \
  | grep -v 'int_powerschool__ps_adaadm_daily_ctod.sql' \
  | xargs sed -i 's/ref("int_powerschool__calendar_week")/ref("int_students__calendar_week")/g'
```

`int_powerschool__ps_adaadm_daily_ctod.sql` is excluded deliberately — Task 11
removes its `calendar_week` join entirely when the calcs move out. Confirm the
sweep:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
grep -rc 'ref("int_powerschool__calendar_week")' --include='*.sql' src/dbt/kipptaf/models/ | grep -v ':0$'
```

Expected: only `int_powerschool__ps_adaadm_daily_ctod.sql` still matches.

- [ ] **Step 4: Build and verify NJ parity**

```bash
uv run dbt build --select int_students__calendar_week+1 \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kipptaf \
  --defer --state src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS.

```sql
select
  'dev' as src, _dbt_source_project, count(*) as n,
  count(distinct format('%T|%T|%T', schoolid, yearid, week_start_date)) as n_keys
from `teamster-332318.zz_<your-github-user>_kipptaf_students.int_students__calendar_week`
where _dbt_source_project != 'kippmiami'
group by 1, 2
union all
select
  'prod', _dbt_source_project, count(*),
  count(distinct format('%T|%T|%T', schoolid, yearid, week_start_date))
from `teamster-332318.kipptaf_powerschool.int_powerschool__calendar_week`
where _dbt_source_project != 'kippmiami'
group by 1, 2
order by 2, 1
```

Expected: identical `n` and `n_keys` per NJ project.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C . diff --name-only HEAD | while read -r f; do [ -f "$f" ] && printf '%s ' "$f"; done) </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add -u && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/kipptaf/models/students/intermediate/int_students__calendar_week.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__calendar_week.yml && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(kipptaf): add int_students__calendar_week and repoint 17 refs

Refs #4924"
```

---

### Task 11: Thin the ctod wrapper, add `int_students__attendance_daily`, repoint 11 refs

The largest task. It moves roughly 200 lines of derived calcs from the
PowerSchool wrapper into the SIS-neutral model.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__ps_adaadm_daily_ctod.sql`
  (reduce to a thin wrapper)
- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__attendance_daily.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__attendance_daily.yml`
- Modify: 11 consumer files

**Interfaces:**

- Consumes: `int_powerschool__ps_adaadm_daily_ctod` (thin),
  `int_focus__attendance_daily` (kipptaf wrapper), `int_students__terms`,
  `int_students__calendar_week`, `int_focus__schools`,
  `stg_google_sheets__people__locations`
- Produces: `int_students__attendance_daily` with every column the current
  `int_powerschool__ps_adaadm_daily_ctod` emits, plus `att_code_focus STRING`

- [ ] **Step 1: Reduce the PowerSchool wrapper to a thin union**

Replace the entire contents of
`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__ps_adaadm_daily_ctod.sql`
with:

```sql
-- Thin PowerSchool union only. Every derived flag, anchor, and running calc that
-- used to live here moved to int_students__attendance_daily, so there is one
-- definition over the SIS-neutral union rather than one per branch. The window
-- partitions were already scoped by _dbt_source_project, so computing them
-- post-union is arithmetically identical.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

- [ ] **Step 2: Write `int_students__attendance_daily`**

Create
`src/dbt/kipptaf/models/students/intermediate/int_students__attendance_daily.sql`.
The `calcs`, `anchors`, and `running_calcs` CTEs and the final select are lifted
verbatim from the pre-change `int_powerschool__ps_adaadm_daily_ctod`, with three
edits: `memberships` becomes the union, `int_powerschool__calendar_week` becomes
`int_students__calendar_week`, and the six unsourceable flags are nulled for
Miami.

```sql
with
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    focus_years as (
        select distinct yearid, from {{ ref("int_focus__attendance_daily") }}
    ),

    -- Year-scoped, not project-scoped. Focus starts at AY2026 and the frozen
    -- archive holds Miami AY2020 through AY2025, so excluding kippmiami outright
    -- (the way int_students__terms does) would delete six years of history.
    powerschool_conformed as (
        select *,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where
            not (
                _dbt_source_project = 'kippmiami'
                and yearid in (select yearid from focus_years)
            )
    ),

    focus_conformed as (
        select
            ad.* except (schoolid),

            fs.schoolid,
        from {{ ref("int_focus__attendance_daily") }} as ad
        inner join focus_schools as fs on ad.schoolid = fs.focus_school_id
    ),

    memberships as (
        select *,
        from powerschool_conformed

        full union all corresponding

        select *,
        from focus_conformed
    ),

    calcs as (
        select
            mem._dbt_source_relation,
            mem._dbt_source_project,
            mem.studentid,
            mem.student_number,
            mem.schoolid,
            mem.entrydate,
            mem.calendardate,
            mem.fteid,
            mem.attendance_conversion_id,
            mem.grade_level,
            mem.ontrack,
            mem.offtrack,
            mem.student_track,
            mem.yearid,
            mem.att_code,
            mem.att_code_focus,
            mem.attendancevalue,
            mem.potential_attendancevalue,
            mem.membershipvalue,

            t.academic_year,
            t.semester,
            t.term,

            cw.week_start_monday,
            cw.week_end_sunday,
            cw.week_number_academic_year,

            abs(mem.attendancevalue - 1) as is_absent,

            -- TODO(#4927): Focus records tardies only at period grain, so
            -- is_tardy, is_ontime, and is_present_weighted's tardy weighting
            -- have no Miami source. Null rather than a fabricated 0 or 1 so
            -- Miami is excluded from network tardy metrics rather than reading
            -- as a verified zero.
            if(
                mem._dbt_source_project = 'kippmiami' and mem.att_code_focus is not null,
                null,
                if(mem.att_code like 'T%', 1.0, 0.0)
            ) as is_tardy,
            if(
                mem._dbt_source_project = 'kippmiami' and mem.att_code_focus is not null,
                null,
                if(mem.att_code like 'T%', 0.0, 1.0)
            ) as is_ontime,
            if(
                mem.att_code like 'T%', 0.67, mem.attendancevalue
            ) as is_present_weighted,

            -- TODO(#4927): Focus attendance carries no suspension codes at any
            -- grain. Miami suspension data lives in DeansList and is not sourced
            -- here. Null so a network suspension rate excludes Miami rather than
            -- diluting itself with false zeros.
            if(
                mem._dbt_source_project = 'kippmiami' and mem.att_code_focus is not null,
                null,
                if(mem.att_code in ('OS', 'OSS', 'OSSP', 'SHI'), 1.0, 0.0)
            ) as is_oss,
            if(
                mem._dbt_source_project = 'kippmiami' and mem.att_code_focus is not null,
                null,
                if(mem.att_code in ('S', 'ISS'), 1.0, 0.0)
            ) as is_iss,
            if(
                mem._dbt_source_project = 'kippmiami' and mem.att_code_focus is not null,
                null,
                if(
                    mem.att_code in ('OS', 'OSS', 'OSSP', 'S', 'ISS', 'SHI'), 1.0, 0.0
                )
            ) as is_suspended,
            if(
                mem._dbt_source_project = 'kippmiami' and mem.att_code_focus is not null,
                null,
                if(
                    mem.att_code not in ('ISS', 'OSS', 'OS', 'OSSP', 'SHI'),
                    abs(mem.attendancevalue - 1),
                    0.0
                )
            ) as is_absent_non_susp,

            -- A day that has actually occurred (<= today). The membership_reg
            -- calendar join emits a row for every in-session day in the
            -- enrollment span, including future year-end days; point-in-time
            -- anchors must ignore those or they latch onto the future last day
            -- of the year and collapse to zero once the fact filters to
            -- calendardate <= current_date.
            mem.calendardate
            <= current_date('{{ var("local_timezone") }}') as is_realized,

        from memberships as mem
        inner join
            {{ ref("int_students__terms") }} as t
            on mem.yearid = t.yearid
            and mem.schoolid = t.schoolid
            and mem.calendardate between t.term_start_date and t.term_end_date
            and mem._dbt_source_project = t._dbt_source_project
            and t.term is not null
        inner join
            {{ ref("int_students__calendar_week") }} as cw
            on mem.yearid = cw.yearid
            and mem.schoolid = cw.schoolid
            and mem.calendardate between cw.week_start_monday and cw.week_end_sunday
            and mem._dbt_source_project = cw._dbt_source_project
    ),
```

Then append the `anchors`, `running_calcs`, and final `select` blocks **exactly
as they appear in the pre-change `int_powerschool__ps_adaadm_daily_ctod`**, with
`att_code_focus` added to the final select list. Retrieve them with:

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer \
  show HEAD:src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__ps_adaadm_daily_ctod.sql \
  | sed -n '/anchors as (/,$p'
```

Do not retype them — copy them, so the NJ arithmetic cannot drift.

- [ ] **Step 3: Write the properties file**

Create
`src/dbt/kipptaf/models/students/intermediate/properties/int_students__attendance_daily.yml`:

```yaml
models:
  - name: int_students__attendance_daily
    description: >-
      SIS-neutral daily attendance membership across the network — the successor
      to int_powerschool__ps_adaadm_daily_ctod, which is now a thin PowerSchool
      union. Holds every derived flag, point-in-time anchor, and running calc
      for both SIS branches, so there is one definition rather than one per
      branch. The PowerSchool branch is year-scoped, so the frozen Miami archive
      keeps serving AY2020 through AY2025 while Focus serves AY2026 forward. Six
      flags are null for Miami because Focus has no day-grain source for them —
      see #4927.
    columns:
      - name: student_number
        description: Network student number.
        config:
          meta:
            contains_pii: true
        data_tests:
          - not_null:
              config:
                severity: error
      - name: calendardate
        description: In-session calendar date the membership row represents.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: studentid
        description: >-
          PowerSchool internal student id. Null for every Miami row — Phase 1
          left it unpopulated for Focus, so joins use student_number.
      - name: att_code
        description: >-
          Attendance code in the PowerSchool vocabulary. Focus codes are
          conformed upstream (U becomes A; AE and AD match; a missing record
          becomes M).
      - name: att_code_focus
        description: >-
          Raw Focus daily code, null on every PowerSchool row. Doubles as the
          marker for which rows carry the #4927 null flags.
      - name: is_tardy
        description: >-
          1 tardy, 0 not. Null for Focus-sourced Miami rows — Focus records
          tardies only at period grain. See #4927.
      - name: is_ontime
        description: >-
          1 on time, 0 tardy. Null for Focus-sourced Miami rows. See #4927.
      - name: is_oss
        description: >-
          1 out-of-school suspension, 0 not. Null for Focus-sourced Miami rows —
          Focus carries no suspension codes. See #4927.
      - name: is_iss
        description: >-
          1 in-school suspension, 0 not. Null for Focus-sourced Miami rows. See
          #4927.
      - name: is_suspended
        description: >-
          1 suspended, 0 not. Null for Focus-sourced Miami rows. See #4927.
      - name: is_absent_non_susp
        description: >-
          1 absent for a non-suspension reason. Null for Focus-sourced Miami
          rows. See #4927.
      - name: _dbt_source_project
        description: Originating district project.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              [student_number, _dbt_source_project, calendardate]
          config:
            severity: error
```

- [ ] **Step 4: Repoint all 11 refs**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
grep -rl 'ref("int_powerschool__ps_adaadm_daily_ctod")' --include='*.sql' src/dbt/kipptaf/models/ \
  | xargs sed -i 's/ref("int_powerschool__ps_adaadm_daily_ctod")/ref("int_students__attendance_daily")/g'
```

Confirm zero remain:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
grep -rc 'ref("int_powerschool__ps_adaadm_daily_ctod")' --include='*.sql' src/dbt/kipptaf/models/ | grep -v ':0$' || echo "none remain"
```

Expected: `none remain`.

- [ ] **Step 5: Build and verify NJ parity — the blocking gate**

```bash
uv run dbt build --select int_students__attendance_daily \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kipptaf \
  --defer --state src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS including the uniqueness test.

NJ must be row-identical AND value-identical to prod:

```sql
select
  'dev' as src, _dbt_source_project, academic_year, count(*) as n,
  sum(membershipvalue) as mem, sum(attendancevalue) as att, sum(is_absent) as absent
from `teamster-332318.zz_<your-github-user>_kipptaf_students.int_students__attendance_daily`
where _dbt_source_project != 'kippmiami'
group by 1, 2, 3
union all
select
  'prod', _dbt_source_project, academic_year, count(*),
  sum(membershipvalue), sum(attendancevalue), sum(is_absent)
from `teamster-332318.kipptaf_powerschool.int_powerschool__ps_adaadm_daily_ctod`
where _dbt_source_project != 'kippmiami'
group by 1, 2, 3
order by 2, 3, 1
```

Expected: every `dev` row matches its `prod` row on `n`, `mem`, `att`, and
`absent`. **Any mismatch blocks the task** — it means the calcs drifted when
they moved.

Then confirm Miami arrived:

```sql
select academic_year, count(*) as n, count(distinct student_number) as students,
  min(calendardate) as first_day, max(calendardate) as last_day
from `teamster-332318.zz_<your-github-user>_kipptaf_students.int_students__attendance_daily`
where _dbt_source_project = 'kippmiami'
group by 1 order by 1
```

Expected: AY2020 through AY2025 present from the archive, and a new AY2026 row
with `first_day` 2026-08-12 and about 1,559 students.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C . diff --name-only HEAD | while read -r f; do [ -f "$f" ] && printf '%s ' "$f"; done) \
  src/dbt/kipptaf/models/students/intermediate/int_students__attendance_daily.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__attendance_daily.yml </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add -u && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/kipptaf/models/students/intermediate/int_students__attendance_daily.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__attendance_daily.yml && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(kipptaf): add int_students__attendance_daily and thin the ctod wrapper

Refs #4924
Refs #4927"
```

---

### Task 12: `int_students__ada`, `int_students__attendance_streak`, and the streak join key

**Files:**

- Create: `src/dbt/kipptaf/models/students/intermediate/int_students__ada.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__attendance_streak.sql`
- Create: properties yml for both
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__attendance_interventions.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_streaks.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__absence_streak_roster.sql`

**Interfaces:**

- Consumes: `int_powerschool__ada`, `int_focus__ada`,
  `int_powerschool__attendance_streak`, `int_focus__attendance_streak`
- Produces: `int_students__ada` and `int_students__attendance_streak`, each with
  the PowerSchool column set plus `_dbt_source_project`

- [ ] **Step 1: Write both union models**

`int_students__ada.sql`:

```sql
with
    focus_years as (select distinct yearid, from {{ ref("int_focus__ada") }}),

    powerschool_conformed as (
        select *,
        from {{ ref("int_powerschool__ada") }}
        where
            not (
                _dbt_source_project = 'kippmiami'
                and yearid in (select yearid from focus_years)
            )
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from {{ ref("int_focus__ada") }}
```

`int_students__attendance_streak.sql`:

```sql
with
    -- int_focus__attendance_streak carries no yearid-only scoping problem: the
    -- Focus branch only holds years Focus covers, so the PowerSchool side is
    -- scoped against those years exactly as elsewhere.
    focus_years as (
        select distinct yearid, from {{ ref("int_focus__attendance_streak") }}
    ),

    powerschool_conformed as (
        select *,
        from {{ ref("int_powerschool__attendance_streak") }}
        where
            not (
                _dbt_source_project = 'kippmiami'
                and yearid in (select yearid from focus_years)
            )
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from {{ ref("int_focus__attendance_streak") }}
```

- [ ] **Step 2: Write both properties files**

`properties/int_students__ada.yml`:

```yaml
models:
  - name: int_students__ada
    description: >-
      SIS-neutral per-student-per-year attendance rollup — the successor to
      int_powerschool__ada, which stays a pure PowerSchool union. The
      PowerSchool branch is year-scoped so the frozen Miami archive keeps
      serving the years Focus does not cover.
    columns:
      - name: student_number
        description: Network student number.
        config:
          meta:
            contains_pii: true
      - name: studentid
        description: PowerSchool internal student id. Null for Miami rows.
      - name: yearid
        description: Academic year minus 1990.
      - name: ada
        description: Average daily attendance across realized membership days.
      - name: _dbt_source_project
        description: Originating district project.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              [student_number, yearid, _dbt_source_project]
          config:
            severity: error
```

`properties/int_students__attendance_streak.yml`:

```yaml
models:
  - name: int_students__attendance_streak
    description: >-
      SIS-neutral consecutive-day attendance streaks — the successor to
      int_powerschool__attendance_streak, which stays a pure PowerSchool union.
      The Focus branch keys its streak_id on student_number rather than
      studentid, which is null for Focus, so the two branches occupy disjoint
      hash spaces and no NJ streak key changes.
    columns:
      - name: streak_id
        description: Surrogate key for the streak.
      - name: student_number
        description: Network student number.
        config:
          meta:
            contains_pii: true
      - name: studentid
        description: PowerSchool internal student id. Null for Miami rows.
      - name: yearid
        description: Academic year minus 1990.
      - name: att_code
        description: >-
          The attendance code for a code streak, or the stringified attendance
          value for a value streak.
      - name: _dbt_source_project
        description: Originating district project.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [streak_id, att_code, _dbt_source_project]
          config:
            severity: error
```

- [ ] **Step 3: Repoint the four refs**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
grep -rl 'ref("int_powerschool__ada")' --include='*.sql' src/dbt/kipptaf/models/ \
  | xargs sed -i 's/ref("int_powerschool__ada")/ref("int_students__ada")/g' && \
grep -rl 'ref("int_powerschool__attendance_streak")' --include='*.sql' src/dbt/kipptaf/models/ \
  | xargs sed -i 's/ref("int_powerschool__attendance_streak")/ref("int_students__attendance_streak")/g'
```

- [ ] **Step 4: Change the streak fact's join key from `studentid` to
      `student_number`**

`studentid` is null on all 10,047 Miami rows of
`int_students__student_enrollment_union`, so a `studentid` join excludes Miami
by construction. `studentid` and `student_number` are strictly 1:1 in every NJ
region (Newark 18,148, Camden 5,510, Paterson 1,051 — identical distinct and
pair counts), so the swap cannot fan out or drop an NJ row.

In `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_streaks.sql`, make
three edits.

First, the `enrollments_raw` select list — replace `studentid,` with
`student_number,` only if `student_number` is not already selected; it is, so
delete the `studentid,` line.

Second, the dedupe partition:

```sql
    enrollments as (
        {{
            dbt_utils.deduplicate(
                relation="enrollments_raw",
                partition_by="student_number, yearid, entrydate, _dbt_source_project",
                order_by="exitdate desc",
            )
        }}
    )
```

Third, the join:

```sql
from {{ ref("int_students__attendance_streak") }} as st
inner join
    enrollments as enr
    on st.student_number = enr.student_number
    and st.yearid = enr.yearid
    and st.streak_start_date >= enr.entrydate
    and st.streak_start_date < enr.exitdate
    and st._dbt_source_project = enr._dbt_source_project
```

Also update the `TODO(#4835)` comment above `enrollments` so it reads
`student_number, yearid, entrydate, _dbt_source_project` instead of
`studentid, yearid, entrydate, _dbt_source_project`.

- [ ] **Step 5: Build and verify NJ parity on the fact**

```bash
uv run dbt build --select int_students__ada int_students__attendance_streak \
  fct_student_attendance_streaks int_students__attendance_interventions \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kipptaf \
  --defer --state src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS, including the fact's primary-key test — that test is what proves
the `student_number` join did not fan out.

```sql
select
  'dev' as src, count(*) as n,
  count(distinct student_attendance_streak_key) as n_keys
from `teamster-332318.zz_<your-github-user>_kipptaf_marts.fct_student_attendance_streaks`
where academic_year <= 2025
union all
select 'prod', count(*), count(distinct student_attendance_streak_key)
from `teamster-332318.kipptaf_marts.fct_student_attendance_streaks`
where academic_year <= 2025
```

Expected: `n` and `n_keys` identical between `dev` and `prod`, and `n = n_keys`
in both. A higher `dev` `n` means the join fanned out.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C . diff --name-only HEAD | while read -r f; do [ -f "$f" ] && printf '%s ' "$f"; done) \
  src/dbt/kipptaf/models/students/intermediate/int_students__ada.sql \
  src/dbt/kipptaf/models/students/intermediate/int_students__attendance_streak.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__ada.yml \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__attendance_streak.yml </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add -u && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/kipptaf/models/students/intermediate/int_students__ada.sql \
  src/dbt/kipptaf/models/students/intermediate/int_students__attendance_streak.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__ada.yml \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__attendance_streak.yml && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(kipptaf): add int_students__ada and __attendance_streak, key the streak fact on student_number

Refs #4924"
```

---

### Task 13: `int_students__calendar_rollup` and the null-safe track join

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__calendar_rollup.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__calendar_rollup.yml`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ops_dashboard.sql:178-182`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__csgf_enrollment.sql:4`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__nj_school_register.sql:54`

**Interfaces:**

- Consumes: `int_powerschool__calendar_rollup`, `int_focus__calendar_rollup`,
  `int_focus__schools`, `stg_google_sheets__people__locations`
- Produces: `int_students__calendar_rollup` with `schoolid INT64` (network
  number), `yearid INT64`, `track STRING`, `min_calendardate DATE`,
  `max_calendardate DATE`, `days_total INT64`, `days_remaining INT64`,
  `_dbt_source_project STRING`

- [ ] **Step 1: Write the model**

```sql
with
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    focus_years as (
        select distinct yearid, from {{ ref("int_focus__calendar_rollup") }}
    ),

    powerschool_conformed as (
        select *,
        from {{ ref("int_powerschool__calendar_rollup") }}
        where
            not (
                _dbt_source_project = 'kippmiami'
                and yearid in (select yearid from focus_years)
            )
    ),

    focus_conformed as (
        select
            cr.* except (schoolid),

            fs.schoolid,
        from {{ ref("int_focus__calendar_rollup") }} as cr
        inner join focus_schools as fs on cr.schoolid = fs.focus_school_id
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
```

- [ ] **Step 2: Write the properties file**

Create
`src/dbt/kipptaf/models/students/intermediate/properties/int_students__calendar_rollup.yml`:

```yaml
models:
  - name: int_students__calendar_rollup
    description: >-
      SIS-neutral per-school-per-year instructional day totals — the successor
      to int_powerschool__calendar_rollup, which stays a pure PowerSchool union.
      The PowerSchool branch emits one row per calendar track; the Focus branch
      emits one row per school-year with a null track, because Focus has no
      track concept and Miami's track is already null on every network
      enrollment row.
    columns:
      - name: schoolid
        description: Network school number.
      - name: yearid
        description: Academic year minus 1990.
      - name: track
        description: >-
          PowerSchool calendar track (A through F), or null for Focus-sourced
          rows.
      - name: days_total
        description: Total in-session days in the school year.
      - name: days_remaining
        description: In-session days still in the future as of today.
      - name: _dbt_source_project
        description: Originating district project.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              [schoolid, yearid, track, _dbt_source_project]
          config:
            severity: error
```

- [ ] **Step 3: Repoint the three consumers, making the ops dashboard join
      null-safe**

`rpt_tableau__nj_school_register.sql` line 54 — ref swap only. It already
filters `region != 'Miami'`, so it never reads a Focus row:

```sql
    {{ ref("int_students__calendar_rollup") }} as d
```

`rpt_gsheets__csgf_enrollment.sql` line 4 — ref swap only. It averages
`days_total` grouped by `yearid` and `schoolid`, so a single null-track Focus
row per school-year is exactly what it needs:

```sql
        from {{ ref("int_students__calendar_rollup") }}
```

`rpt_tableau__ops_dashboard.sql` lines 178-182 — ref swap plus a null-safe track
predicate. `se.track` is null on all 3,253 Miami rows of
`int_extracts__student_enrollments`, and the Focus rollup emits a null track, so
a plain `=` would never match and Miami would still get no calendar:

```sql
left join
    {{ ref("int_students__calendar_rollup") }} as cal
    on se.schoolid = cal.schoolid
    and se.yearid = cal.yearid
    and se.track is not distinct from cal.track
    and se._dbt_source_project = cal._dbt_source_project
```

This cannot newly match an NJ row: the PowerSchool branch derives `track` by
unpivoting the calendar-day track columns where the value is 1, so it never
emits a null track for NJ to pair with.

- [ ] **Step 4: Build and verify**

```bash
uv run dbt build --select int_students__calendar_rollup rpt_tableau__ops_dashboard \
  rpt_gsheets__csgf_enrollment rpt_tableau__nj_school_register \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kipptaf \
  --defer --state src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS.

Confirm the null-safe join did not change NJ, then that Miami gained a calendar:

```sql
select
  _dbt_source_project,
  count(*) as n,
  countif(total_instructional_days is null) as n_null_days
from `teamster-332318.zz_<your-github-user>_kipptaf_tableau.rpt_tableau__ops_dashboard`
group by 1 order by 1
```

Expected: NJ `n_null_days` unchanged from prod (run the same query against
`kipptaf_tableau.rpt_tableau__ops_dashboard` to compare), and Miami's
`n_null_days` lower than prod's, because Miami AY2026 rows now resolve a
calendar.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C . diff --name-only HEAD | while read -r f; do [ -f "$f" ] && printf '%s ' "$f"; done) \
  src/dbt/kipptaf/models/students/intermediate/int_students__calendar_rollup.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__calendar_rollup.yml </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add -u && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add \
  src/dbt/kipptaf/models/students/intermediate/int_students__calendar_rollup.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__calendar_rollup.yml && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "feat(kipptaf): add int_students__calendar_rollup with a null-safe track join

Refs #4924"
```

---

### Task 14: Rewrite the chronic absenteeism log

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__attendance_chronic_absenteeism_log.sql:14-27`

**Interfaces:**

- Consumes: `int_students__attendance_daily` instead of
  `stg_powerschool__attendance` and `stg_powerschool__attendance_code`
- Produces: unchanged output columns

- [ ] **Step 1: Replace the two staging joins with one**

The report currently joins `co.studentid = att.studentid`, which excludes Miami
because `studentid` is null there. Replace the two `inner join` blocks (lines 14
through 27) with a single join on `int_students__attendance_daily`, keeping the
`att_code like 'A%'` predicate — the `U` to `A` mapping makes it correct for
Miami:

```sql
            count(att.calendardate) as n_absences,
        from {{ ref("int_extracts__student_enrollments") }} as co
        inner join
            {{ ref("int_students__attendance_daily") }} as att
            on co.student_number = att.student_number
            and att.calendardate between co.entrydate and co.exitdate
            and co._dbt_source_project = att._dbt_source_project
            -- 'A%' covers A, AD, and AE. Focus's U is conformed to A upstream,
            -- so Miami is counted by the same predicate rather than a branch.
            and att.att_code like 'A%'  -- change to exclude AE
```

The `att.att_mode_code = 'ATT_ModeDaily'` filter is dropped: the new upstream is
already daily grain, so the filter has nothing to exclude.

- [ ] **Step 2: Build and verify**

```bash
uv run dbt build --select rpt_tableau__attendance_chronic_absenteeism_log \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kipptaf \
  --defer --state src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS.

```sql
select region, count(*) as n, sum(n_absences) as absences
from `teamster-332318.zz_<your-github-user>_kipptaf_tableau.rpt_tableau__attendance_chronic_absenteeism_log`
group by 1 order by 1
```

Expected, measured against prod AY2025 before this plan was executed:

| Region   | Old    | New    | Delta |
| -------- | ------ | ------ | ----- |
| Camden   | 25,730 | 25,730 | 0     |
| Newark   | 66,970 | 66,968 | -2    |
| Paterson | 5,772  | 5,772  | 0     |
| Miami    | none   | 289    | +289  |

NJ is effectively unchanged. The 29% row-drop in the kipptaf ctod does not reach
this predicate, because absences essentially always fall inside a quarter term
and a mapped calendar week. Newark's -2 of 66,970 is 0.003%.

Treat any NJ delta beyond those exact figures as a defect and investigate before
committing — not as acceptable drift.

Miami gains rows in the ARCHIVE years too, not only AY2026: the old
`co.studentid = att.studentid` join excluded Miami in every year because
`studentid` is null for Focus-sourced enrollment. That is a side-effect fix, and
it means Miami appears in this report for AY2020 onward.

- [ ] **Step 3: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__attendance_chronic_absenteeism_log.sql </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer add -u && \
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer commit -m "fix(kipptaf): source the chronic absenteeism log from int_students__attendance_daily

Refs #4924"
```

---

### Task 15: Whole-graph validation and PR2

**Files:** none — this is the validation gate.

- [ ] **Step 1: Confirm no stale refs remain**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
grep -rn 'ref("int_powerschool__\(ps_adaadm_daily_ctod\|calendar_week\|calendar_rollup\|attendance_streak\|ada\)")' \
  --include='*.sql' src/dbt/kipptaf/models/ || echo "no stale refs"
```

Expected: `no stale refs`. The thin `int_powerschool__ps_adaadm_daily_ctod`
model still exists as a file; nothing but `int_students__attendance_daily` may
`ref()` it, and that ref lives in the `int_students__` model, so this grep
should return nothing from any other file.

- [ ] **Step 2: `--empty` build across the whole descendant graph**

```bash
uv run dbt build --empty --select int_students__attendance_daily+ \
  int_students__calendar_week+ int_students__calendar_day+ \
  int_students__calendar_rollup+ int_students__ada+ \
  int_students__attendance_streak+ \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kipptaf \
  --defer --state src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS on every node. This proves column resolution across all 32
repointed files. It does NOT prove values — Steps 4 and 5 of Tasks 9 through 14
did that.

- [ ] **Step 3: Confirm `fct_student_attendance_daily` reports Miami**

```bash
uv run dbt build --select fct_student_attendance_daily \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer/src/dbt/kipptaf \
  --defer --state src/dbt/kipptaf/target/prod --target dev
```

```sql
select
  academic_year,
  count(*) as n,
  countif(attendance_value is null) as n_null_att,
  avg(attendance_value) as ada
from `teamster-332318.zz_<your-github-user>_kipptaf_marts.fct_student_attendance_daily` as f
inner join `teamster-332318.kipptaf_marts.dim_students` as s
  on f.student_enrollment_key = s.student_enrollment_key
where s.region = 'Miami'
group by 1 order by 1
```

If `dim_students` has no `region`, join `dim_student_enrollments` instead and
filter on its region column. Expected: an AY2026 row with non-null `ada` between
0.90 and 1.00, where prod has no AY2026 Miami row at all.

- [ ] **Step 4: Lint the whole PR**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C . diff --name-only origin/main...HEAD | while read -r f; do [ -f "$f" ] && printf '%s ' "$f"; done) </dev/null
```

Expected: `No issues`. Background this — a `--force` check over 40-odd files
takes more than two minutes, and its progress spinner emits no result lines, so
an early grep reads as a false clean.

- [ ] **Step 5: Push and open PR2**

Confirm dbt Cloud CI is in a terminal state before pushing — a push cancels an
in-progress run and restarts it.

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-attendance-network-layer push
```

Open PR2 using `.github/pull_request_template.md`. The body must include:

- `Refs #4924`, `Refs #4927`, `Refs #4803`
- That Task 8 Step 3's `dbt clone --target staging` was run, and by whom
- That the `int_students__calendar_day` Ops warn test is expected to WARN on the
  two closed Miami schools, and why that is correct rather than a failure
- The NJ parity evidence from Tasks 9 through 14 — the actual counts, not a
  claim that they matched

- [ ] **Step 6: After CI passes, fetch warnings and re-measure #4803**

Fetch CI warnings with
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` before calling
the PR done. Then re-measure the #4803 orphan count against the PR-branch schema
and post the new number as a comment on #4803:

```sql
select count(*) as orphans
from `teamster-332318.dbt_cloud_pr_<job_id>_<pr_num>_marts.fct_student_attendance_daily` as f
left join `teamster-332318.kipptaf_marts.dim_student_enrollments` as d
  on f.student_enrollment_key = d.student_enrollment_key
where d.student_enrollment_key is null
```

Expected: the count moves but does not reach zero — Focus carries AY2026-27
forward only, so the AY2025 archive leg of #4803 is untouched by this work.

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: the six package models to
Tasks 1 through 6; source declarations and passthroughs to Task 8; the six
`int_students__*` models to Tasks 9 through 13; the ctod restructure to Task 11;
the two join-key changes to Tasks 12 and 14; the 37 repoints across Tasks 9
through 14; NJ parity, Miami presence, the dbt tests, `--empty`, and the #4803
re-measure to Tasks 9 through 15; the two-PR ship sequence to Tasks 7 and 15;
the `TODO(#4927)` nulls to Task 11. The Ops calendar handoff needs no task — it
is an Asana item — but its warn test is in Task 9.

**Type consistency.** `int_focus__attendance_daily` produces `att_code_focus`,
which Task 11 reads to gate the six null flags, and which Task 11's properties
file documents. `student_number` is the join key in Tasks 12 and 14 and is
produced by every model from Task 1 onward. `yearid` is the year-scoping key in
every union and is produced by all six package models. `schoolid` is Focus
internal in Tasks 1 through 6 and the network number from Task 9 onward, with
the crosswalk CTE spelled out in each task that needs it.

**Task 14's NJ risk was measured, not assumed.** The rewrite changes the join
key from `studentid` to `student_number` and drops the `att_mode_code` filter,
and the kipptaf ctod is a 29% filtered subset of the district data, so NJ counts
could have fallen. Measured against prod AY2025 they do not: Camden and Paterson
are identical, and Newark moves by 2 rows out of 66,970. Task 14 carries those
exact figures as its gate rather than a tolerance band.
