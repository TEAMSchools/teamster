# Attendance Period Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a period-grain attendance fact carrying the corrected chronic
absence definition, then collapse the Cube measure families and delete the
`queryRewrite` snapshot block.

**Architecture:** One new dbt mart, `fct_student_attendance_periods`, holding
one row per student per school per period (`year`, `month`, `week`) with
cumulative year-to-date attendance accumulated through that period's last
membership day. Chronic absence, ADA tier, and truancy are resolved once in dbt.
Cube reads the new fact through a new cube and view and computes nothing. No
Tesseract feature is used.

**Tech Stack:** dbt (BigQuery), Cube semantic layer, `uv` for all Python.

**Spec:**
`docs/superpowers/specs/2026-08-26-attendance-period-snapshot-design.md`

## Global Constraints

- Chronically absent when ADA is **at or below 90.0%**, evaluated on accumulated
  integer counts, never on an averaged float.
- Eligible at **10 or more cumulative membership days at the individual
  school**, not per period.
- Mid-year leavers are included. A period with no membership day produces no
  row.
- Tier 1 is 95% and above, Tier 2 is **strictly above** 90.0% to below 95%, Tier
  3 is 80% through 90.0% inclusive, Tier 4 is below 80%.
- `is_chronically_absent` is derived from `ada_tier`, never computed separately.
- Grain is `(student_key, location_key, period_type, period_start_date)`.
- The New Jersey 45-day threshold is out of scope (#5015).
- SQL follows `.trunk/config/.sqlfluff`: BigQuery dialect, lowercase keywords,
  trailing commas, single quotes, 88-character lines.
- Always `uv run dbt ...`, never a bare `dbt`.
- Do not run `trunk fmt` or `trunk check` manually; the pre-commit hook formats.
- The new fact is materialized as a table on a nightly cron, matching the
  precedent set by `int_topline__ada_running_weekly` (#4153) and
  `fct_assessment_scores_enrollment_scoped` (#4468). Exact block, in the
  properties yml under `models: - name: ...`:

  ```yaml
  config:
    materialized: table
    meta:
      dagster:
        # Table, not the marts-default view. Every attendance-star model in
        # prod is a view today, so a Cube query re-expands the whole chain —
        # the #4333 defect that #4468 fixed for the assessment star. Nightly
        # cron rather than eager: the upstreams are eager and would drive
        # repeated rebuilds of a 3.6M row model for no freshness anyone
        # consumes. Midnight tick matches int_topline__ada_running_weekly,
        # the closest sibling off the same upstream, and the KIPP Foundation
        # criteria require nightly refresh, not intra-day.
        automation_condition:
          cron_schedule: 0 0 * * *
  ```

  Marts default to view: the kipptaf `marts:` block sets only `+schema` and
  `+contract`. Do not rely on it.

---

## Prior art — read before Task 1

A topline refactor landed 2026-08-20 through 08-25 and overlaps this work. Read
these before writing any SQL.

| Model                                     | What it already does                                                                                                                                                                     |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `int_students__attendance_daily`          | Added 2026-08-20 (`03ee12f77`) as the shared daily base. This plan sources from it.                                                                                                      |
| `int_topline__ada_running_weekly`         | Running attendance and membership sums partitioned by `(student_number, academic_year, schoolid)`, ordered by `week_start_monday`. The same accumulation this plan needs, at week grain. |
| `int_topline__truancy_weekly`             | Truancy per `(student, school, year, week)`.                                                                                                                                             |
| `int_extracts__student_enrollments_weeks` | A week spine, left joined so an enrolled week with no attendance still gets a row.                                                                                                       |
| `int_students__calendar_week`             | Added 2026-08-20 (`cb443b90c`), 17 refs repointed.                                                                                                                                       |

Two things follow.

**The grain is confirmed.** Topline independently partitions on
`(student_number, academic_year, schoolid)` — student and school, not the
enrollment stint. That is the grain this plan uses, arrived at separately, and
it carries the Miami `student_number` keying fix from `d8530569c`. Do not
re-litigate it.

**Three definitions conflict, and they must not multiply.** Shipping this
snapshot without reconciling them creates a fourth running-ADA implementation,
after `fct_student_attendance_daily._running_ada`,
`int_topline__ada_running_weekly.ada_running`, and
`rpt_tableau__attendance_dashboard` (which has its own open defect, #3948, for
partitioning on `studentid` rather than `student_number` — the same bug topline
fixed).

| Conflict    | Topline                                                    | This plan                                 |
| ----------- | ---------------------------------------------------------- | ----------------------------------------- |
| Denominator | all membership values                                      | `membershipvalue = 1` only                |
| Precision   | `round(safe_divide(...), 3)`                               | integer comparison, never a rounded float |
| Truancy     | `max(is_truant)` over the period, so "truant at any point" | value as of `period_end_date`             |
| Year scope  | current and prior academic year only                       | all years present in the fact             |

The rounding one matters most: rounding to 3 decimals puts a float boundary at
exactly `0.900`, which is the defect class this whole effort exists to remove.

This plan does **not** subsume the topline models. They have their own consumers
(`int_topline__student_metrics`, `rpt_gsheets__school_metrics_extract`) and
their own owner. Task 9 decides what happens to them.

A note on the spine: topline left joins a week spine so an enrolled week with no
attendance still produces a row. This plan deliberately does the opposite — no
membership day, no row — so a withdrawn student cannot carry forward as a stale
value. That is the spec's decision, not an oversight. Do not swap in the spine
pattern without changing the spec.

---

### Task 1: Period snapshot model, year period only

Start with one period type so the accumulation logic is provable before the
period spine multiplies the rows.

**Files:**

- Create:
  `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_periods.sql`
- Create:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_periods.yml`

**Interfaces:**

- Consumes: `ref("int_students__attendance_daily")` for `student_number`,
  `_dbt_source_project`, `schoolid`, `academic_year`, `calendardate`,
  `week_start_monday`, `membershipvalue`, `attendancevalue`, `is_truant`.
  `ref("int_students__schools")` for `location_key`, joined on
  `school_number = schoolid` and `_dbt_source_project`, exactly as
  `dim_student_enrollments.sql:27-30` does.
- Produces: `fct_student_attendance_periods` with columns
  `student_attendance_period_key` (string), `student_key` (string),
  `location_key` (string), `academic_year` (int64), `period_type` (string),
  `period_start_date` (date), `period_end_date` (date), `n_membership_days_ytd`
  (numeric), `n_present_days_ytd` (numeric).

- [ ] **Step 1: Write the failing unit test**

Add to `properties/fct_student_attendance_periods.yml`:

```yaml
unit_tests:
  - name: test_periods_year_accumulates_all_membership_days
    description:
      One student, one school, three membership days in AY2025. The year row
      must accumulate every day and end on the last membership day, not the last
      calendar day.
    model: fct_student_attendance_periods
    given:
      - input: ref('int_students__attendance_daily')
        format: sql
        rows: |
          select
            123456 as student_number,
            'kippnewark' as _dbt_source_project,
            100 as schoolid,
            2025 as academic_year,
            date '2025-09-02' as calendardate,
            date '2025-09-01' as week_start_monday,
            1.0 as membershipvalue,
            1.0 as attendancevalue,
            false as is_truant
          union all
          select
            123456, 'kippnewark', 100, 2025, date '2025-09-03',
            date '2025-09-01', 1.0, 0.0, false
          union all
          select
            123456, 'kippnewark', 100, 2025, date '2025-09-04',
            date '2025-09-01', 1.0, 1.0, false
      - input: ref('int_students__schools')
        format: sql
        rows: |
          select
            100 as school_number,
            'kippnewark' as _dbt_source_project,
            'loc-abc' as location_key
    expect:
      format: sql
      rows: |
        select
          'loc-abc' as location_key,
          2025 as academic_year,
          'year' as period_type,
          date '2025-07-01' as period_start_date,
          date '2025-09-04' as period_end_date,
          3.0 as n_membership_days_ytd,
          2.0 as n_present_days_ytd
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run dbt test \
  --select fct_student_attendance_periods \
  --project-dir src/dbt/kipptaf
```

Expected: FAIL — the model does not exist yet.

- [ ] **Step 3: Write the model**

Create `fct_student_attendance_periods.sql`:

```sql
with
    daily as (
        select
            ada.student_number,
            ada._dbt_source_project,
            ada.academic_year,
            ada.calendardate,
            ada.membershipvalue,
            ada.attendancevalue,
            ada.is_truant,

            sch.location_key,

            date(ada.academic_year, 7, 1) as year_start_date,
        from {{ ref("int_students__attendance_daily") }} as ada
        inner join
            {{ ref("int_students__schools") }} as sch
            on ada.schoolid = sch.school_number
            and ada._dbt_source_project = sch._dbt_source_project
        where
            ada.calendardate
            <= current_date('{{ var("local_timezone") }}')
    ),

    aggregated as (
        select
            location_key,
            student_number,
            _dbt_source_project,
            academic_year,

            'year' as period_type,
            year_start_date as period_start_date,

            max(if(membershipvalue = 1, calendardate, null))
            as period_end_date,

            sum(
                if(
                    membershipvalue = 1 and attendancevalue is not null,
                    membershipvalue,
                    0
                )
            ) as n_membership_days_ytd,

            sum(
                if(
                    membershipvalue = 1 and attendancevalue is not null,
                    attendancevalue,
                    0
                )
            ) as n_present_days_ytd,
        from daily
        group by
            location_key,
            student_number,
            _dbt_source_project,
            academic_year,
            period_type,
            period_start_date
        having max(if(membershipvalue = 1, calendardate, null)) is not null
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "_dbt_source_project",
                "location_key",
                "period_type",
                "period_start_date",
            ]
        )
    }} as student_attendance_period_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    location_key,
    academic_year,
    period_type,
    period_start_date,
    period_end_date,
    n_membership_days_ytd,
    n_present_days_ytd,
from aggregated
```

Add the matching `models:` block to the properties yml above the `unit_tests:`
block, with a `description` for every column and a `unique` data test on
`student_attendance_period_key`.

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run dbt test \
  --select fct_student_attendance_periods \
  --project-dir src/dbt/kipptaf
```

Expected: PASS.

- [ ] **Step 5: Build the model against real data and eyeball the row count**

```bash
uv run dbt build \
  --select fct_student_attendance_periods \
  --project-dir src/dbt/kipptaf
```

Expected: builds clean. Row count for `period_type = 'year'` should be close to
14,498 for AY2025 — that is the student-school pair count measured on #4994.

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_student_attendance_periods.sql \
  src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_periods.yml
git commit -m "feat(dbt): add attendance period snapshot, year period

Refs #4994"
```

---

### Task 2: Add the month and week periods

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_periods.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_periods.yml`

**Interfaces:**

- Consumes: Task 1's model.
- Produces: the same columns, now with `period_type` in
  `('year', 'month', 'week')`. `n_membership_days_ytd` and `n_present_days_ytd`
  accumulate from the start of the academic year through each period's
  `period_end_date`, not within the period.

- [ ] **Step 1: Write the failing unit test**

Append to `unit_tests:`:

```yaml
- name: test_periods_month_accumulates_year_to_date
  description:
    One student with two membership days in September and one in October. The
    October month row must carry all three days, because chronic absence is a
    year-to-date measure, not a per-month one.
  model: fct_student_attendance_periods
  given:
    - input: ref('int_students__attendance_daily')
      format: sql
      rows: |
        select
          123456 as student_number,
          'kippnewark' as _dbt_source_project,
          100 as schoolid,
          2025 as academic_year,
          date '2025-09-02' as calendardate,
          date '2025-09-01' as week_start_monday,
          1.0 as membershipvalue,
          1.0 as attendancevalue,
          false as is_truant
        union all
        select
          123456, 'kippnewark', 100, 2025, date '2025-09-03',
          date '2025-09-01', 1.0, 1.0, false
        union all
        select
          123456, 'kippnewark', 100, 2025, date '2025-10-06',
          date '2025-10-06', 1.0, 0.0, false
    - input: ref('int_students__schools')
      format: sql
      rows: |
        select
          100 as school_number,
          'kippnewark' as _dbt_source_project,
          'loc-abc' as location_key
  expect:
    format: sql
    rows: |
      select
        'month' as period_type,
        date '2025-09-01' as period_start_date,
        date '2025-09-03' as period_end_date,
        2.0 as n_membership_days_ytd,
        2.0 as n_present_days_ytd
      union all
      select
        'month', date '2025-10-01', date '2025-10-06', 3.0, 2.0
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run dbt test \
  --select fct_student_attendance_periods \
  --project-dir src/dbt/kipptaf
```

Expected: FAIL — only `year` rows exist.

- [ ] **Step 3: Add the period spine and the cumulative window**

Replace the `aggregated` CTE with a spine plus a per-period aggregate plus a
cumulative window. `period_start_date` for `week` is the PowerSchool school week
(`week_start_monday`), never a derived ISO week.

```sql
    spine as (
        select
            d.*,
            period.period_type,
            case period.period_type
                when 'year' then d.year_start_date
                when 'month' then date_trunc(d.calendardate, month)
                when 'week' then d.week_start_monday
            end as period_start_date,
        from daily as d
        cross join
            unnest(['year', 'month', 'week']) as period_type
            with offset as period_offset
    ),

    per_period as (
        select
            location_key,
            student_number,
            _dbt_source_project,
            academic_year,
            period_type,
            period_start_date,

            max(if(membershipvalue = 1, calendardate, null))
            as period_end_date,

            sum(
                if(
                    membershipvalue = 1 and attendancevalue is not null,
                    membershipvalue,
                    0
                )
            ) as n_membership_days_period,

            sum(
                if(
                    membershipvalue = 1 and attendancevalue is not null,
                    attendancevalue,
                    0
                )
            ) as n_present_days_period,
        from spine
        group by
            location_key,
            student_number,
            _dbt_source_project,
            academic_year,
            period_type,
            period_start_date
        having max(if(membershipvalue = 1, calendardate, null)) is not null
    ),

    aggregated as (
        select
            * except (n_membership_days_period, n_present_days_period),

            sum(n_membership_days_period) over (
                partition by
                    location_key,
                    student_number,
                    _dbt_source_project,
                    academic_year,
                    period_type
                order by period_start_date asc
                rows between unbounded preceding and current row
            ) as n_membership_days_ytd,

            sum(n_present_days_period) over (
                partition by
                    location_key,
                    student_number,
                    _dbt_source_project,
                    academic_year,
                    period_type
                order by period_start_date asc
                rows between unbounded preceding and current row
            ) as n_present_days_ytd,
        from per_period
    )
```

The `cross join unnest` uses `with offset` so sqlfluff does not flag an
unreferenced alias; the offset column is not selected.

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run dbt test \
  --select fct_student_attendance_periods \
  --project-dir src/dbt/kipptaf
```

Expected: PASS, including Task 1's year test unchanged.

- [ ] **Step 5: Build and check the row count against the spec estimate**

```bash
uv run dbt build \
  --select fct_student_attendance_periods \
  --project-dir src/dbt/kipptaf
```

Expected: under 750,000 rows total. If it is far above, the period spine is
fanning out — check that `week_start_monday` is the school week and not null.

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_student_attendance_periods.sql \
  src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_periods.yml
git commit -m "feat(dbt): add month and week periods to the attendance snapshot

Refs #4994"
```

---

### Task 3: Tier, chronic absence, eligibility, and truancy

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_periods.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_periods.yml`

**Interfaces:**

- Consumes: Task 2's `n_membership_days_ytd`, `n_present_days_ytd`.
- Produces: added columns `ada_tier` (string), `is_chronically_absent` (bool),
  `is_ca_eligible` (bool), `is_truant` (bool). `is_chronically_absent` is
  `ada_tier in ('Tier 3', 'Tier 4')`.

- [ ] **Step 1: Write the failing boundary tests**

Append to `unit_tests:`. These are the boundaries every defect on #4994 sat on.

```yaml
- name: test_periods_boundaries
  description:
    Four students on the exact boundaries. 9 of 10 present is exactly 90.0
    percent and must be chronically absent and Tier 3, never Tier 2. 19 of 20 is
    95 percent and must be Tier 1. A student with 9 membership days is not
    eligible; 10 is. Truancy is read from the last membership day.
  model: fct_student_attendance_periods
  given:
    - input: ref('int_students__attendance_daily')
      format: sql
      rows: |
        select
          1 as student_number,
          'kippnewark' as _dbt_source_project,
          100 as schoolid,
          2025 as academic_year,
          d as calendardate,
          date '2025-09-01' as week_start_monday,
          1.0 as membershipvalue,
          if(d = date '2025-09-10', 0.0, 1.0) as attendancevalue,
          false as is_truant
        from unnest(generate_date_array(
          date '2025-09-01', date '2025-09-10'
        )) as d
        union all
        select
          2, 'kippnewark', 100, 2025, d, date '2025-09-01', 1.0,
          if(d = date '2025-09-20', 0.0, 1.0), true
        from unnest(generate_date_array(
          date '2025-09-01', date '2025-09-20'
        )) as d
        union all
        select
          3, 'kippnewark', 100, 2025, d, date '2025-09-01', 1.0, 1.0, false
        from unnest(generate_date_array(
          date '2025-09-01', date '2025-09-09'
        )) as d
    - input: ref('int_students__schools')
      format: sql
      rows: |
        select
          100 as school_number,
          'kippnewark' as _dbt_source_project,
          'loc-abc' as location_key
  expect:
    format: sql
    rows: |
      select
        1 as student_number_probe,
        'Tier 3' as ada_tier,
        true as is_chronically_absent,
        true as is_ca_eligible,
        false as is_truant
      union all
      select 2, 'Tier 1', false, true, true
      union all
      select 3, 'Tier 1', false, false, false
```

The model exposes `student_key`, not `student_number`, so the `expect` block
compares on the same surrogate key the model builds. In a dbt unit test the
`expect` rows are compared to the model's output columns by name, so compute it
the same way the model does:

```sql
select
  to_hex(md5(cast(1 as string))) as student_key,
  'Tier 3' as ada_tier,
  true as is_chronically_absent,
  true as is_ca_eligible,
  false as is_truant
```

`dbt_utils.generate_surrogate_key` on BigQuery is `to_hex(md5(...))` over the
fields joined by `'-'`, with nulls coalesced to
`'_dbt_utils_surrogate_key_null_'`. With a single non-null field that reduces to
`to_hex(md5(cast(<field> as string)))`. Verify by running
`uv run dbt compile --select fct_student_attendance_periods` and reading the
generated key expression rather than trusting this note.

- [ ] **Step 1b: Write the remaining four boundary tests from the spec**

The spec lists eight boundary cases. Step 1 covers exactly-90.0 percent, the
Tier 3 placement, and the 10-versus-9-day threshold. These four are the rest,
and each one guards a defect measured on #4994.

```yaml
- name: test_periods_ninety_point_zero_one_is_not_chronically_absent
  description:
    The threshold is at or below 90.0 percent, so just above it is not
    chronically absent. 91 of 101 present is 90.099 percent.
  model: fct_student_attendance_periods
  given:
    - input: ref('int_students__attendance_daily')
      format: sql
      rows: |
        select
          1 as student_number,
          'kippnewark' as _dbt_source_project,
          100 as schoolid,
          2025 as academic_year,
          d as calendardate,
          date '2025-09-01' as week_start_monday,
          1.0 as membershipvalue,
          if(
            d <= date_add(date '2025-09-01', interval 9 day), 0.0, 1.0
          ) as attendancevalue,
          false as is_truant
        from unnest(generate_date_array(
          date '2025-09-01', date '2025-12-10'
        )) as d
    - input: ref('int_students__schools')
      format: sql
      rows: |
        select
          100 as school_number,
          'kippnewark' as _dbt_source_project,
          'loc-abc' as location_key
  expect:
    format: sql
    rows: |
      select 'Tier 2' as ada_tier, false as is_chronically_absent

- name: test_periods_threshold_is_per_school_not_combined
  description:
    Six membership days at each of two schools. Twelve days combined, but the
    threshold applies per school, so the student is eligible at neither.
  model: fct_student_attendance_periods
  given:
    - input: ref('int_students__attendance_daily')
      format: sql
      rows: |
        select
          1 as student_number,
          'kippnewark' as _dbt_source_project,
          100 as schoolid,
          2025 as academic_year,
          d as calendardate,
          date '2025-09-01' as week_start_monday,
          1.0 as membershipvalue,
          1.0 as attendancevalue,
          false as is_truant
        from unnest(generate_date_array(
          date '2025-09-01', date '2025-09-06'
        )) as d
        union all
        select
          1, 'kippnewark', 200, 2025, d, date '2025-10-06', 1.0, 1.0, false
        from unnest(generate_date_array(
          date '2025-10-06', date '2025-10-11'
        )) as d
    - input: ref('int_students__schools')
      format: sql
      rows: |
        select 100 as school_number, 'kippnewark' as _dbt_source_project,
          'loc-a' as location_key
        union all
        select 200, 'kippnewark', 'loc-b'
  expect:
    format: sql
    rows: |
      select 'loc-a' as location_key, false as is_ca_eligible
      union all
      select 'loc-b', false

- name: test_periods_mid_year_leaver_keeps_own_period_end
  description: A student whose last membership day is 10 October gets an October
    row dated 10 October, no November row, and a year row. This is the 180-
    enrollment defect on #4994.
  model: fct_student_attendance_periods
  given:
    - input: ref('int_students__attendance_daily')
      format: sql
      rows: |
        select
          1 as student_number,
          'kippnewark' as _dbt_source_project,
          100 as schoolid,
          2025 as academic_year,
          d as calendardate,
          date_trunc(d, week(monday)) as week_start_monday,
          1.0 as membershipvalue,
          1.0 as attendancevalue,
          false as is_truant
        from unnest(generate_date_array(
          date '2025-09-01', date '2025-10-10'
        )) as d
    - input: ref('int_students__schools')
      format: sql
      rows: |
        select
          100 as school_number,
          'kippnewark' as _dbt_source_project,
          'loc-abc' as location_key
  expect:
    format: sql
    rows: |
      select
        'month' as period_type,
        date '2025-10-01' as period_start_date,
        date '2025-10-10' as period_end_date
      union all
      select 'month', date '2025-09-01', date '2025-09-30'

- name: test_periods_eligibility_is_cumulative_not_per_period
  description:
    Forty membership days through September, then six in October. The October
    row is eligible on 46 cumulative days, even though October alone has six.
    Applying the threshold per period would wrongly exclude a short month.
  model: fct_student_attendance_periods
  given:
    - input: ref('int_students__attendance_daily')
      format: sql
      rows: |
        select
          1 as student_number,
          'kippnewark' as _dbt_source_project,
          100 as schoolid,
          2025 as academic_year,
          d as calendardate,
          date_trunc(d, week(monday)) as week_start_monday,
          1.0 as membershipvalue,
          1.0 as attendancevalue,
          false as is_truant
        from unnest(generate_date_array(
          date '2025-08-01', date '2025-09-30'
        )) as d
        union all
        select
          1, 'kippnewark', 100, 2025, d, date_trunc(d, week(monday)),
          1.0, 1.0, false
        from unnest(generate_date_array(
          date '2025-10-01', date '2025-10-06'
        )) as d
    - input: ref('int_students__schools')
      format: sql
      rows: |
        select
          100 as school_number,
          'kippnewark' as _dbt_source_project,
          'loc-abc' as location_key
  expect:
    format: sql
    rows: |
      select
        'month' as period_type,
        date '2025-10-01' as period_start_date,
        true as is_ca_eligible
```

The `test_periods_mid_year_leaver_keeps_own_period_end` case uses
`date_trunc(d, week(monday))` for the week bucket only because these fixtures
have no school calendar. Production reads `week_start_monday` from
`int_students__attendance_daily`, which is the PowerSchool school week — never
derive it.

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run dbt test \
  --select fct_student_attendance_periods \
  --project-dir src/dbt/kipptaf
```

Expected: FAIL — `ada_tier` does not exist.

- [ ] **Step 3: Add the derived columns**

Add `is_truant` to the `per_period` aggregate, reading the last membership day:

```sql
            array_agg(
                if(membershipvalue = 1, is_truant, null) ignore nulls
                order by calendardate desc
                limit 1
            )[safe_offset(0)] as is_truant,
```

Then in the final `select`, one tier expression with chronic absence derived
from it. Integer comparison, so the 198 enrollments at exactly 90.0 percent sort
deterministically instead of by float representation.

```sql
    case
        when n_membership_days_ytd = 0
        then null
        when n_present_days_ytd * 100 >= n_membership_days_ytd * 95
        then 'Tier 1'
        when n_present_days_ytd * 10 > n_membership_days_ytd * 9
        then 'Tier 2'
        when n_present_days_ytd * 10 >= n_membership_days_ytd * 8
        then 'Tier 3'
        else 'Tier 4'
    end as ada_tier,

    n_membership_days_ytd >= 10 as is_ca_eligible,
```

`is_chronically_absent` cannot reference `ada_tier` in the same `select`, so
wrap the final select in one more CTE and derive it there:

```sql
select
    * except (ada_tier),
    ada_tier,
    ada_tier in ('Tier 3', 'Tier 4') as is_chronically_absent,
from tiered
```

The `n_membership_days_ytd = 0` guard is load-bearing: without it `0 >= 0` makes
an enrollment with no membership days Tier 3.

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run dbt test \
  --select fct_student_attendance_periods \
  --project-dir src/dbt/kipptaf
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_student_attendance_periods.sql \
  src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_periods.yml
git commit -m "feat(dbt): derive tier, chronic absence, eligibility, truancy

Chronic absence derives from ada_tier so the two cannot disagree at
exactly 90.0 percent.

Refs #4994"
```

---

### Task 4: Reconcile against the production figures

The spec's whole claim is that specific numbers move by specific amounts. Prove
it before touching Cube.

**The model is not in `kipptaf_marts`.** A local `dbt build` writes to the
developer's own schema, and the new fact only reaches prod after merge and a
prod run. Every query in this task reads
`zz_cristinabaldor_kipptaf_marts.fct_student_attendance_periods`. Comparisons
against the OLD measures still read
`kipptaf_marts.fct_student_attendance_daily`, so a reconciliation query joins
across the two schemas — that is correct, not a mistake to 'fix' by pointing
both at one schema.

**Files:**

- Create: `.claude/scratch/reconcile_period_snapshot.sql` (throwaway,
  gitignored)

**Interfaces:**

- Consumes: the built `fct_student_attendance_periods` and the existing
  `fct_student_attendance_daily`.
- Produces: a verified reconciliation posted to #4994. No code artifact.

- [ ] **Step 1: Count AY2025 year-period chronic absence from the new fact**

```sql
select
  countif(is_chronically_absent and is_ca_eligible) as ca,
  countif(is_ca_eligible) as eligible,
  round(
    100 * countif(is_chronically_absent and is_ca_eligible)
    / countif(is_ca_eligible), 2
  ) as pct
from zz_cristinabaldor_kipptaf_marts.fct_student_attendance_periods
where academic_year = 2025 and period_type = 'year'
```

Expected: roughly 26.2 percent, against 24.8 percent shipped today. The exact
figure will differ from #4994's because that measurement used the stint grain
and omitted the 10-day threshold; document whatever it is.

- [ ] **Step 2: Verify the four movements individually**

Each number on #4994 must be attributable:

- 180 mid-year leavers now present that the year-end anchor excluded.
- 119 enrollments at exactly 90.0 percent now chronically absent.
- 147 enrollments under 10 membership days now excluded.
- 73 same-school re-enrollments now accumulated together rather than split.

Write one query per movement comparing the new fact against
`fct_student_attendance_daily` filtered the old way. If a count does not
reconcile, stop and investigate before proceeding — a silent mismatch here is
the whole risk this plan exists to avoid.

- [ ] **Step 3: Verify month and week counts did NOT move**

The spec predicts month and week figures are unchanged, because the existing
`is_month_end_record` and `is_week_end_record` anchors are already per stint and
already land on a membership day. Compare `count_chronically_absent_month_end`
and `count_chronically_absent_week_end` against the new fact for AY2025 at both
grains.

Expected: equal, except for the 73 re-enrollment cases and the 10-day
exclusions. Quantify any residual before proceeding.

- [ ] **Step 4: Post the reconciliation to the issue**

Post a comment on #4994 with a before-and-after table for each movement. This is
the audit trail for a change to a figure that feeds state accountability.

- [ ] **Step 5: Commit nothing**

This task produces no code. Delete the scratch SQL.

---

### Task 5: Cube cube and view for the snapshot

**Files:**

- Create:
  `src/cube/model/cubes/student_attendance/student_attendance_periods.yml`
- Create:
  `src/cube/model/views/student_attendance/student_attendance_periods_view.yml`

**Interfaces:**

- Consumes: `kipptaf_marts.fct_student_attendance_periods`.
- Produces: view `student_attendance_periods_view` exposing measures
  `count_students`, `count_chronically_absent`, `pct_chronically_absent`,
  `pct_tier_1_2`, `pct_tier_3`, `count_truants`, `pct_truant`, and dimensions
  `period_type`, `period_start_date`, `period_end_date`, `ada_tier`.

- [ ] **Step 1: Write the cube**

`public: false` at the cube level, per `src/cube/CLAUDE.md`. One dbt model in
`sql_table`, no joins beyond conformed dims. Measures are plain `count_distinct`
filtered on the dbt-resolved flags — Cube computes nothing.

```yaml
cubes:
  - name: student_attendance_periods
    public: false
    sql_table: kipptaf_marts.fct_student_attendance_periods

    joins:
      - name: dates
        sql: "{dates.date_key} = {CUBE}.period_end_date_key"
        relationship: many_to_one

      - name: locations
        sql: "{locations.location_key} = {CUBE}.location_key"
        relationship: many_to_one

    dimensions:
      - name: student_attendance_period_key
        sql: student_attendance_period_key
        type: string
        primary_key: true
        public: false

      - name: period_type
        description: >-
          Selects the grain: year, month, or week. Week is the PowerSchool
          school week. No anchor filter is needed or accepted.
        sql: period_type
        type: string
        public: true

      - name: ada_tier
        sql: ada_tier
        type: string
        public: true

    measures:
      - name: _count_eligible
        sql: student_key
        type: count_distinct
        public: false
        filters:
          - sql: "{CUBE}.is_ca_eligible"

      - name: count_chronically_absent
        sql: student_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.is_ca_eligible"
          - sql: "{CUBE}.is_chronically_absent"

      - name: pct_chronically_absent
        sql: "1.0 * {count_chronically_absent} / NULLIF({_count_eligible}, 0)"
        type: number
        format: percent
        public: true
```

Add `pct_tier_1_2`, `pct_tier_3`, `count_truants`, and `pct_truant` on the same
pattern, each filtering `is_ca_eligible` so numerator and denominator share a
population.

- [ ] **Step 2: Write the view with a routing description**

The description is LLM-facing through the MCP `meta` tool, so state the routing
rule explicitly.

```yaml
views:
  - name: student_attendance_periods_view
    description: >-
      Attendance rates as of the end of a period — chronic absence, ADA tier,
      and truancy. Set period_type to year, month, or week and group by
      period_start_date. No anchor filter is needed or accepted; the row already
      is the period-end value. A row exists only for a period in which the
      student had a membership day at that school, so a withdrawn student stops
      appearing rather than carrying forward, and a trend's denominator shifts
      between points. For day-level questions — was a student absent on a given
      date, a calendar heatmap, day-of-week patterns — use
      student_attendance_view instead.
```

- [ ] **Step 3: Start the dev server and query both views**

```bash
cd src/cube && npm run dev
```

Then query `pct_chronically_absent` grouped by `period_start_date` with
`period_type = 'year'`, and confirm it matches Task 4's reconciled figure.

- [ ] **Step 4: Add the exposure**

Add `ref("fct_student_attendance_periods")` to
`src/dbt/kipptaf/models/exposures/cube.yml`, alongside the existing
`fct_student_attendance_daily` entry at line 77.

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/cubes/student_attendance/student_attendance_periods.yml \
  src/cube/model/views/student_attendance/student_attendance_periods_view.yml \
  src/dbt/kipptaf/models/exposures/cube.yml
git commit -m "feat(cube): add the attendance period snapshot cube and view

Refs #4994"
```

---

### Task 6: Named measures on `student_enrollments`

Do this before Task 7. It is what lets the `queryRewrite` block empty completely
rather than shrink.

**Files:**

- Modify: `src/cube/model/cubes/students/student_enrollments.yml`
- Modify: `src/cube/model/views/students/student_enrollments_view.yml`
- Modify: `src/cube/cube.js:210-215`

**Interfaces:**

- Consumes: the `is_current_record`, `is_enrollment_month_end_record`, and
  `is_enrollment_week_end_record` dimensions the cube already exposes.
- Produces: measures `count_students_year_end`, `count_students_month_end`,
  `count_students_week_end`.

- [ ] **Step 1: Add the three named measures**

`count_students` is a distinct count, so it never duplicates a student. What the
anchor fixes is the metric: unanchored, a range returns everyone enrolled at any
point in it rather than a point-in-time headcount.

```yaml
- name: count_students_year_end
  description: >-
    Point-in-time headcount as of each school's most recent in-session day.
    Anchor baked in — no filter required.
  sql: "{student_school_enrollments.student_key}"
  type: count_distinct
  public: true
  filters:
    - sql: "{CUBE}.is_current_record"
```

Repeat for `_month_end` filtering `is_enrollment_month_end_record` and
`_week_end` filtering `is_enrollment_week_end_record`.

- [ ] **Step 2: Expose them on the view**

Add all three to the `includes:` list in `student_enrollments_view.yml`.

- [ ] **Step 3: Remove the `student_enrollments` stem from the guard**

In `cube.js`, delete `"student_enrollments"` from `SNAPSHOT_CUBES` and delete
the `student_enrollments` key from `SNAPSHOT_MEASURE_STEMS`. Leave
`SNAPSHOT_ANCHOR_OVERRIDES` alone for now; Task 7 removes it with the rest.

- [ ] **Step 4: Verify against the old behaviour**

With the dev server running, compare `count_students_year_end` against the old
unanchored `count_students` with an injected anchor, for AY2025 and by month.

Expected: identical. If they differ, the wrong flag is filtered.

- [ ] **Step 5: Run the hook regression tests and the cube unit tests**

```bash
cd src/cube && node --test cube.test.js
bash tests/hooks/run_all.sh
```

Expected: PASS. `cube.test.js` covers the auth hooks, not `queryRewrite`, so it
should be unaffected — if it fails, the edit reached further than intended.

- [ ] **Step 6: Commit**

```bash
git add src/cube/model/cubes/students/student_enrollments.yml \
  src/cube/model/views/students/student_enrollments_view.yml
git commit -m "feat(cube): named period-end headcount measures on enrollments

count_students is a distinct count and never duplicated a student; the
anchor selects the metric, not the deduplication. Three named measures
replace the queryRewrite injection for this cube.

Refs #4994"
```

`cube.js` is a protected path — stage it with `git add -u` and commit it
manually, per `.claude/CLAUDE.md`.

---

### Task 7: Retire the attendance measure families and the `queryRewrite` block

**Files:**

- Modify: `src/cube/model/cubes/student_attendance/student_attendance.yml`
- Modify: `src/cube/model/views/student_attendance/student_attendance_view.yml`
- Modify: `src/cube/cube.js:178-215` and `src/cube/cube.js:448-573`

**Interfaces:**

- Consumes: Task 5's view, which now answers every period-end question.
- Produces: `student_attendance_view` exposing only day-level members. `cube.js`
  exporting `driverFactory`, `contextToGroups`, `checkAuth`, `checkSqlAuth`, and
  `canSwitchSqlUser` — no `queryRewrite`.

- [ ] **Step 1: Delete the 30 measures**

Remove every measure whose name ends in `_year_end`, `_month_end`, or
`_week_end` from `student_attendance.yml`, and their entries from the view's
`includes:`. That is 10 per suffix: 7 chronic-absence and tier measures plus 3
truancy.

Keep the base `count_chronically_absent`, `pct_chronically_absent`,
`pct_tier_1_2`, `pct_tier_3`, `count_truants`, and `pct_truant`? **No.** Delete
those too — they only had meaning under anchor injection. Day-level attendance
questions do not need a chronic absence measure, and the snapshot view owns the
rate.

Keep `count_students`, `avg_daily_attendance`, `pct_tardy`, `pct_ontime`, and
`count_absent_days`, which are point-in-time safe and additive.

- [ ] **Step 2: Delete the anchor dimensions**

Remove `is_latest_record`, `is_month_end_record`, `is_week_end_record`, and
`is_chronically_absent` and `ada_tier` from `student_attendance.yml` and from
the view. Nothing reads them once the families are gone, and leaving them
invites someone to rebuild the anchor pattern by hand.

- [ ] **Step 3: Delete the `queryRewrite` snapshot block**

Remove `SNAPSHOT_ANCHOR_DIMENSIONS`, `SNAPSHOT_ANCHOR_OVERRIDES`,
`SNAPSHOT_SELF_ANCHORED_SUFFIXES`, `SNAPSHOT_CUBES`, `SNAPSHOT_MEASURE_STEMS`,
and the entire `queryRewrite` export. Both stems are now gone, so the function
body is empty and the export goes with it.

- [ ] **Step 4: Run the cube tests and the RLS matrix**

```bash
cd src/cube && node --test cube.test.js && node --test access.test.js
```

Then the row-level security sign-off with auth on, per `src/cube/CLAUDE.md` —
dev mode downgrades a denial to a silent zero rows, which makes a dev-mode
matrix falsely benign:

```bash
cd src/cube && NODE_ENV=production CUBEJS_DEV_MODE=false npm run dev
```

Run `scripts/cube_rls_matrix.py` against the SQL API across a viewer matrix and
confirm both views scope correctly. The new view carries student identifiers, so
it needs the same `access_policy` gating as `student_attendance_view` — verify a
school-scoped viewer sees only their school.

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/cubes/student_attendance/student_attendance.yml \
  src/cube/model/views/student_attendance/student_attendance_view.yml
git add -u
git commit -m "refactor(cube): retire the anchor measure families and queryRewrite

30 period-end measures and 165 lines of anchor-injection logic are
replaced by the period snapshot view. cube.js keeps only authentication,
access, and emulation.

Refs #4994"
```

---

### Task 8: Documentation surfaces

**Files:**

- Modify:
  `src/cube/model/views/student_attendance/student_attendance_view.yml:21-27`
- Modify: `src/cube/mcp/server.py:369-394`
- Modify: `src/cube/CLAUDE.md`

**Interfaces:**

- Consumes: nothing.
- Produces: no stale anchor guidance anywhere an LLM can read it.

- [ ] **Step 1: Replace the attendance view's anchor paragraph**

Lines 21-27 document the whole anchor contract — base measures defaulting to
year-end, a single `date_day` equality filter for point-in-time, `_month_end`
and `_week_end` for trends. Every sentence is now false. Replace with:

```yaml
      This view answers day-level questions: attendance on a specific date, a
      calendar heatmap, day-of-week patterns, per-student daily drill-down. For
      chronic absence, ADA tier, or truancy rates as of a period, use
      student_attendance_periods_view — those measures are not on this view.
```

- [ ] **Step 2: Add the routing rule to the MCP `meta` docstring**

The docstring names the analyst-facing views by example and carries the grain
rules, but has no rule for choosing between two views of one domain. Add, after
the existing view examples:

```text
    Two views can cover one domain at different grains. Attendance splits this
    way: `student_attendance_view` answers day-level questions (was a student
    absent on a date, calendar heatmaps, day-of-week patterns), while
    `student_attendance_periods_view` answers rates as of a period (chronic
    absence, ADA tier, truancy) via its `period_type` dimension. Pick by whether
    the question is about a day or about a period, and do not add an anchor
    filter to either — neither view needs one.
```

- [ ] **Step 3: Update `src/cube/CLAUDE.md`**

Its "Semi-additive / period-end snapshot measures" guidance, if present,
describes the retired pattern. Replace with the rule this work established:
period-end values are materialized in dbt at period grain, and Cube filters a
`period_type` dimension. Note that query-time window functions over the daily
fact were measured and do not scale, with the numbers from the spec.

- [ ] **Step 4: Verify `meta` returns the new guidance**

With the dev server running, call the MCP `meta` tool and confirm both view
descriptions come back and neither mentions an anchor.

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/views/student_attendance/student_attendance_view.yml \
  src/cube/mcp/server.py src/cube/CLAUDE.md
git commit -m "docs(cube): route between the daily and period attendance views

Refs #4994"
```

---

---

### Task 9: Decide what happens to the topline weekly models

Do this last, once the snapshot is proven, and do not start it without the
topline owner in the loop.

**Files:**

- Read:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__ada_running_weekly.sql`
- Read:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__truancy_weekly.sql`
- Read:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__student_metrics.sql`
- Read:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__school_metrics_extract.sql`

**Interfaces:**

- Consumes: the built `fct_student_attendance_periods`.
- Produces: a decision recorded on #4994, and an issue if the answer is to
  repoint.

- [ ] **Step 1: Quantify the disagreement**

For AY2025 at week grain, compare `int_topline__ada_running_weekly.ada_running`
against the snapshot's ADA for the same `(student_number, schoolid, week)`.
Expect differences from all three conflicts in the Prior art table above.
Quantify each separately — how many student-weeks differ from the denominator
choice, how many from rounding, and how many students sit exactly at `0.900`
after topline's rounding but not before it.

- [ ] **Step 2: Do the same for truancy**

Compare `int_topline__truancy_weekly.is_truant_int` against the snapshot's
`is_truant` at week grain. Any difference is the "at any point in the week"
versus "as of week end" semantics, not a bug in either.

- [ ] **Step 3: Take a position and record it**

Three options, and a recommendation is required rather than a list:

1. Repoint topline at the snapshot. One implementation, and topline's numbers
   move. Needs the topline owner's agreement, because it changes a published
   school-metrics extract.
1. Leave topline alone and document that the two answer different questions.
   Cheapest, but leaves four implementations of one metric.
1. Repoint topline and keep its rounding at the presentation layer only, so the
   stored value stays exact.

Post the comparison and the recommendation to #4994.

- [ ] **Step 4: Open an issue if the answer is to repoint**

Repointing topline is its own change with its own blast radius. It does not
belong in this branch.

- [ ] **Step 5: Commit nothing**

This task produces a decision, not code.

## Open items carried out of this plan

- The New Jersey 45-day chronic absence figure (#5015).
- Pre-aggregations. At under 750K rows they may not be needed. Measure the new
  view against the Cube MCP's 55 second poll deadline before deciding; the
  legacy path measured 51.6s, inside that band.
- The KIPP Foundation tier-boundary question: their criteria call Tier 1 and
  Tier 2 on track at 90 percent and above, while defining chronic absence as at
  or below 90.0 percent. We resolve it by starting Tier 2 strictly above 90.0
  percent. Confirm before the figure is reported upward.
- #4803, the 961 orphaned Miami AY2025 enrollment keys. This plan sidesteps it
  by sourcing from `int_students__attendance_daily`, so the snapshot attributes
  those stints to schools correctly while a day-level query through
  `dim_student_enrollments` still cannot.
