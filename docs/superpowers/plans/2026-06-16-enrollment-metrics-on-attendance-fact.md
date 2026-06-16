# Enrollment Metrics on the Attendance Daily Fact — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive point-in-time student enrollment headcount metrics from the
existing `fct_student_attendance_daily` mart instead of a dedicated
`fct_student_enrollment_daily`, and delete that second fact.

**Architecture:** The attendance daily fact already has one row per enrolled
student per attendance-recorded day — verified to reconcile exactly to topline
Total Enrollment (Oct 1 2025 = 10,637, all four districts incl. Paterson 522).
We add **per-school period-end anchor columns** to that fact so a point-in-time
headcount works for as-of-now and month/week trends across all districts
(including Paterson, whose membership is clean), then repoint the existing
`student_enrollments` Cube + views to read it. The enrollment metrics live in a
**separate Cube** (not the `student_attendance` cube) because Cube's snapshot
guard resolves anchor dimensions per-cube and enrollment's per-school anchors
differ from attendance's per-stint, membership-day anchors.

**Tech Stack:** dbt (BigQuery), Cube semantic layer (`cube.js` + YAML), trunk
(sqlfluff/yamllint/markdownlint).

---

## Background & decisions (read before starting)

- **Why not a second fact:** `fct_student_attendance_daily` already contains the
  enrolled-student-day rows. The only structural divergence from an in-session
  calendar spine is Miami's PowerSchool calendar flagging summer (July) days
  in-session with no attendance recorded — those are excluded from the
  attendance fact, which is the desired behavior ("no school in July").
- **Paterson:** the fact previously nulled Paterson's `attendance_value`,
  `membership_value`, and `present_weight` for `academic_year < 2026`. We
  **remove that null-out entirely** — the mart reflects source. Paterson's
  membership is clean; only attendance values are unreliable due to an upstream
  PowerSchool attendance-conversion config gap, tracked in **#4193** (assigned
  to the Paterson team). Do not re-introduce any Paterson special-casing in the
  fact or the cube.
- **The fact carries TWO independent anchor families — see the explicit layout
  below.** Enrollment needs per-school period-end anchors; the existing
  attendance/CA measures use per-stint membership-day anchors. They answer
  different questions, so they are different physical columns.
- **No future-row zero-out:** the attendance fact is capped at `current_date` at
  source (`int_powerschool__ps_adaadm_daily_ctod` has no future rows), so
  `max(date_key) over (...)` always lands on a real row — this is how cbini's
  "point-in-time count reads 0 on a non-session-day rebuild" bug is structurally
  avoided. No `least(..., current_date)` is needed.
- **Cube wiring mostly in place:** `cube.js` already lists `student_enrollments`
  in `SNAPSHOT_CUBES`, maps
  `SNAPSHOT_MEASURE_STEMS.student_enrollments = ["count_students"]`, and sets
  `SNAPSHOT_ANCHOR_OVERRIDES.student_enrollments = { default: "is_current_record" }`.
  The only `cube.js` logic change is the school-week grouping rework (Task 7),
  needed because Cube's native `granularity: "week"` is ISO-only and the week
  anchors are school-week-based.

## Two anchor families (explicit)

`fct_student_attendance_daily` will carry two sets of period-end flags. They are
computed differently and serve different measures. Do not merge or reuse one for
the other.

|                   | Existing — attendance / CA family                                               | New — enrollment family                                                                |
| ----------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Columns           | `is_latest_record`, `is_month_end_record`, `is_week_end_record`                 | `is_current_record`, `is_enrollment_month_end_record`, `is_enrollment_week_end_record` |
| Partition         | per **enrollment stint** (`student_enrollment_key`)                             | per **school** (`schoolid`, `_dbt_source_project`, `academic_year`)                    |
| Day gate          | last **full-membership day** (`membership_value = 1`)                           | school's last **attendance day** (any row)                                             |
| Week bucket       | **school week** (`week_start_monday`) — realigned from ISO in this PR           | **school week** (`week_start_monday`)                                                  |
| Month bucket      | calendar month (`date_trunc(date_key, month)`)                                  | calendar month (`date_trunc(date_key, month)`)                                         |
| Serves            | chronic-absence / ADA-tier / truancy trend measures (`student_attendance` cube) | point-in-time headcount (`student_enrollments` cube)                                   |
| Question answered | "this student's CA status as of their own last day in the period"               | "how many students were enrolled as of the school's last day in the period"            |

Why they cannot be shared — the **mid-period withdrawal** case. A student
withdraws Jan 15:

- Per-stint `is_month_end_record` → TRUE on **Jan 15** (their own last
  membership day) → the withdrawn student is counted in January.
- Per-school enrollment anchor → TRUE on the **school's last January day** (e.g.
  Jan 30) → the withdrawn student has no row that day → correctly **excluded**
  from the as-of-month-end headcount.

A point-in-time roster must exclude someone who already left; the per-stint
anchor would overcount them. Same logic makes `is_current_record` (per-school
latest day) the right default headcount anchor versus the per-stint
`is_latest_record`.

Why new physical columns rather than redefining the existing ones: the per-stint
`is_month_end_record` / `is_week_end_record` are actively consumed by the
`student_attendance` cube's CA/tier/truancy measures. Redefining them would
silently move those numbers. One column cannot hold both meanings.

Why the Cube layer still calls them `is_month_end_record` /
`is_week_end_record`: the snapshot guard injects fixed anchor-dimension names by
query granularity (`cube.js` `SNAPSHOT_ANCHOR_DIMENSIONS`). The
`student_enrollments` cube exposes dimensions with those conventional names
whose `sql:` points at the `is_enrollment_*` columns; the `student_attendance`
cube's same-named dimensions point at the per-stint columns. Each cube resolves
the anchor to its own column because the guard keys the anchor member as
`${cubePrefix}.${anchorDimension}`.

## Week handling — school weeks, both cubes (DECIDED)

Both topline surfaces bucket weeks by the PowerSchool **per-school school week**
`week_start_monday` (already materialized on
`int_powerschool__ps_adaadm_daily_ctod` — no new join): topline enrollment
(`int_extracts__student_enrollments_weeks`, dedups on `week_start_monday`) and
topline attendance (`int_topline__ada_running_weekly`, aggregates on
`week_start_monday`). School weeks are NOT a Monday-Sunday grid — PowerSchool
splits weeks at month/term boundaries, so
`week_start_monday != date_trunc(date_key, week(monday))` for ~14% of days
(verified, Newark + Miami).

**Decision:** every week anchor in this fact uses school weeks, and BOTH cubes'
weekly trends group by a `school_week_start_date` dimension (=
`week_start_monday` cast to timestamp), not Cube's native `granularity: "week"`
(which is ISO-only). This makes the enrollment weekly trend AND the attendance
CA weekly trend consistent with each other and with topline.

This is a live-measure change to the attendance cube's CA `_week_end` family
(`count_chronically_absent_week_end`, `pct_tier_*_week_end`,
`count_truants_week_end`): they move from ISO `granularity: "week"` to the
`school_week_start_date` grouping, and their numbers shift on split weeks.
Validate the magnitude and call it out in the PR (Task 9).

Because Cube's `granularity: "week"` cannot express a school week, the snapshot
guard is reworked (Task 7) to drive the "week" period off the
`school_week_start_date` grouping instead of the ISO granularity:

- A query grouping by `*school_week_start_date` is treated as the week period.
- Base snapshot measures get the week anchor injected on that grouping.
- `_week_end` named measures REQUIRE the `school_week_start_date` grouping (the
  guard throws, pointing there, if a snapshot week measure is requested with
  Cube `granularity: "week"` — the ISO path is removed for snapshot measures).
- `_month_end` / month granularity is unchanged (calendar months are
  unambiguous).

## File map

| File                                                                               | Action                                                                                                                                                |
| ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql`              | Modify — remove Paterson null-out; realign `is_week_end_record` to school weeks; expose `school_week_start_date`; add 3 per-school enrollment anchors |
| `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_daily.yml`   | Modify — add 3 anchor columns; strip "Null for Paterson…" sentences                                                                                   |
| `src/dbt/kipptaf/tests/fct_student_attendance_daily__enrollment_anchor_exists.sql` | Create — anchor-existence test (cbini)                                                                                                                |
| `src/dbt/kipptaf/models/marts/facts/fct_student_enrollment_daily.sql`              | Delete                                                                                                                                                |
| `src/dbt/kipptaf/models/marts/facts/properties/fct_student_enrollment_daily.yml`   | Delete                                                                                                                                                |
| `src/dbt/kipptaf/tests/fct_student_enrollment_daily__*.sql` (5 files)              | Delete                                                                                                                                                |
| `src/cube/model/cubes/students/student_enrollments.yml`                            | Modify — repoint `sql_table`; drop direct `locations` join + `location_key`; remap anchor dims; PK → `student_attendance_daily_key`                   |
| `src/cube/model/views/students/student_enrollments_summary.yml`                    | Modify — locations `join_path` via stints                                                                                                             |
| `src/cube/model/views/students/student_enrollments_detail.yml`                     | Modify — locations `join_path` via stints; PK member rename                                                                                           |
| `src/cube/cube.js`                                                                 | Modify — rework snapshot guard for school-week grouping (both cubes); stems comment                                                                   |
| `src/cube/CLAUDE.md`                                                               | Modify — remove the now-obsolete `student_enrollments` locations-diamond note                                                                         |
| `src/dbt/kipptaf/models/exposures/cube.yml`                                        | Modify — remove `fct_student_enrollment_daily` from `depends_on`                                                                                      |
| `docs/reference/marts-data-models.md`                                              | Regenerate                                                                                                                                            |

Also modified for the attendance CA week realignment (Task 5b):
`src/cube/model/cubes/student_attendance/student_attendance.yml` (add
`school_week_start_date` dimension; CA `_week_end` measures keyed to it) and
`src/cube/model/views/student_attendance/student_attendance_summary.yml` +
`_detail.yml` (expose `school_week_start_date`). The attendance fact SQL/yml
changes (realign `is_week_end_record`, expose `school_week_start_date`) are
folded into Tasks 1-2.

Keep `student_enrollment_stints` (the `dim_student_enrollments` cube rename) —
it is still the join target for `student_key`/location/status and is unaffected.

---

### Task 1: Attendance fact — remove Paterson null-out + add per-school enrollment anchors

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql`

- [ ] **Step 1: Carry the partition columns into the `daily` CTE**

In the `daily` CTE's SELECT, add these four plain refs from the `ada` alias.
`schoolid` / `_dbt_source_project` / `academic_year` are plumbing (window
partitions only, not output); `week_start_monday` is BOTH a window partition AND
exposed as an output column (`school_week_start_date`, Step 5) so the cubes can
group weekly trends by the school week. Place them with the other `ada.` refs,
immediately after the `student_enrollment_key` surrogate-key block:

```sql
            ada.schoolid,
            ada._dbt_source_project,
            ada.academic_year,
            ada.week_start_monday,
```

- [ ] **Step 2: Remove the Paterson null-out (three columns)**

Replace the three `if(... = 'kipppaterson' and ... < 2026, null, ...)` blocks
with the raw source values:

```sql
            ada.attendancevalue as attendance_value,
            ada.membershipvalue as membership_value,

            ada.is_present_weighted as present_weight,
```

(These replace lines ~31-46 of the current model. The mart now reflects source;
Paterson attendance unreliability is tracked upstream in #4193.)

- [ ] **Step 3: Realign the existing `is_week_end_record` to school weeks**

The existing `is_week_end_record` partitions by
`date_trunc(date_key, week(monday))` (ISO week). Change that partition key to
`week_start_monday` (the PowerSchool school week) so the CA weekly trend matches
topline. Keep it per-stint and membership-gated — only the week-bucket key
changes:

```sql
    row_number() over (
        partition by student_enrollment_key, week_start_monday
        order by if(membership_value = 1, date_key, null) desc nulls last
    )
    = 1
    and membership_value = 1 as is_week_end_record,
```

(`is_month_end_record` is unchanged — calendar months are unambiguous.)

- [ ] **Step 4: Expose `school_week_start_date` as an output column**

Add to the final SELECT's output columns (so both cubes can group weekly trends
by the school week). Place with the other date columns:

```sql
    week_start_monday as school_week_start_date,
```

- [ ] **Step 5: Add the per-school enrollment anchors to the final SELECT**

After the existing `is_week_end_record` window expression, append:

```sql
    date_key = max(date_key) over (
        partition by schoolid, _dbt_source_project, academic_year
    ) as is_current_record,

    date_key = max(date_key) over (
        partition by
            schoolid, _dbt_source_project, academic_year, date_trunc(date_key, month)
    ) as is_enrollment_month_end_record,

    date_key = max(date_key) over (
        partition by schoolid, _dbt_source_project, week_start_monday
    ) as is_enrollment_week_end_record,
```

The week anchor partitions by `week_start_monday` (the school week — already the
year/school-scoped bucket, so `academic_year` is redundant here). Columns read
bare (no alias) because the final SELECT reads from a single CTE (`running`),
matching the existing `is_latest_record` / `is_month_end_record` style.

- [ ] **Step 6: Build the model in dev**

Run:
`uv run dbt run --select fct_student_attendance_daily --project-dir src/dbt/kipptaf --target dev`
Expected: success, creating
`zz_<username>_kipptaf_marts.fct_student_attendance_daily`.

- [ ] **Step 7: Reconcile the as-of-now and Oct-1 headcounts (incl. Paterson)**

Run via BigQuery MCP against the dev table (substitute your dev schema):

```sql
-- Oct-1 day-exact headcount must equal topline 10,637 (Camden 2,161 /
-- Miami 1,346 / Newark 6,608 / Paterson 522). count distinct STUDENTS via the
-- stint dim's student_key, not student_enrollment_key (transfers have 2 stints).
select count(distinct d.student_key) as headcount_oct1
from `zz_<username>_kipptaf_marts.fct_student_attendance_daily` as f
inner join `kipptaf_marts.dim_student_enrollments` as d
    on f.student_enrollment_key = d.student_enrollment_key
where f.date_key = '2025-10-01'
```

Expected: `10637`.

```sql
-- Paterson is present (membership no longer nulled): is_current_record count
select countif(f.is_current_record) as n_current_rows
from `zz_<username>_kipptaf_marts.fct_student_attendance_daily` as f
where date_key between '2025-07-01' and current_date('America/New_York')
```

Expected: > 0 and no error.

- [ ] **Step 8: Run trunk on the SQL file**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql`
(run with cwd at the repo root). Expected: no findings. Fix any sqlfluff ST06
column-ordering complaints by grouping the new plain refs per the existing
layout.

- [ ] **Step 9: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql
git commit -m "feat(dbt): per-school enrollment + school-week anchors on fct_student_attendance_daily; drop Paterson null-out"
```

---

### Task 2: Attendance fact properties — document the new anchors, strip Paterson nulls

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_daily.yml`

- [ ] **Step 1: Remove the "Null for Paterson…" sentences**

In the descriptions for `attendance_value`, `membership_value`,
`present_weight`, `is_chronically_absent`, and `ada_tier`, delete the trailing
sentence "Null for Paterson records before academic_year 2026 (excluded from ADA
— data not fully integrated until AY2026)." (and the
`is_chronically_absent`/`ada_tier` variant "Null for Paterson records before
academic_year 2026."). Leave the rest of each description intact.

- [ ] **Step 2: Add the three new anchor columns**

Append after the existing `is_week_end_record` column entry:

```yaml
- name: is_current_record
  data_type: boolean
  description: >-
    TRUE on the school's latest attendance day that has occurred, FALSE
    otherwise. Computed per school, source project, and academic year (the fact
    is capped at today, so this anchors on the most recent in-session day with
    data). Drives the default point-in-time enrollment headcount in the
    student_enrollments cube — counts students enrolled as of the school's last
    day, excluding withdrawn students. Distinct from is_latest_record (which is
    per enrollment stint).

- name: is_enrollment_month_end_record
  data_type: boolean
  description: >-
    TRUE on the school's latest attendance day of each calendar month, FALSE
    otherwise. Computed per school, source project, academic year, and month.
    Use with a month-granularity date dimension for month-over-month
    point-in-time enrollment trends. Independent of is_month_end_record (which
    is per enrollment stint on full membership days, for chronic-absence
    trends).

- name: is_enrollment_week_end_record
  data_type: boolean
  description: >-
    TRUE on the school's latest attendance day of each PowerSchool school week
    (week_start_monday), FALSE otherwise. Computed per school, source project,
    and school week. Group the weekly enrollment trend by school_week_start_date
    (NOT Cube's ISO week granularity) — matches topline school-week buckets.
    Independent of is_week_end_record.

- name: school_week_start_date
  data_type: date
  description: >-
    PowerSchool per-school school-week start (week_start_monday). The
    week-bucket key for both the enrollment weekly trend and the realigned CA
    weekly trend — group weekly snapshots by this, matching topline
    (int_topline__ada_running_weekly and int_extracts__student_enrollments_weeks
    both key on week_start_monday).
  config:
    meta:
      source_system: PowerSchool
      source_model: int_powerschool__ps_adaadm_daily_ctod
      source_column: week_start_monday
```

- [ ] **Step 2c: Update `is_week_end_record`'s description (school-week
      realign)**

The existing `is_week_end_record` column description says it buckets by calendar
week. Update it to: "TRUE on the last full membership day
(`membership_value = 1`) of each **PowerSchool school week**
(`week_start_monday`) per student enrollment … Use by grouping the CA weekly
trend on `school_week_start_date` (the realigned school-week bucket; previously
ISO Monday week)."

- [ ] **Step 2b: Note the Paterson-attendance caveat at model level**

In the model `description:`, add a sentence after the four-measures paragraph:

```text
      Paterson attendance values for AY2025 are known-incomplete due to an
      upstream PowerSchool attendance-conversion gap (#4193); ADA and
      attendance-derived measures reflect source and will correct once that
      config is fixed. Membership and enrollment counts are unaffected.
```

- [ ] **Step 3: Parse to validate the contract**

Run: `uv run dbt parse --project-dir src/dbt/kipptaf --target dev` Expected:
parses clean (the 4 new columns — `school_week_start_date` date + 3 boolean
anchors — match the SQL output).

- [ ] **Step 4: Build with contract enforcement**

Run:
`uv run dbt run --select fct_student_attendance_daily --project-dir src/dbt/kipptaf --target dev`
Expected: success (contract accepts the 4 new columns).

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_daily.yml
git commit -m "docs(dbt): document enrollment anchors; remove Paterson null caveats"
```

---

### Task 3: Anchor-existence test (cbini's requirement) + remove old enrollment tests

**Files:**

- Create:
  `src/dbt/kipptaf/tests/fct_student_attendance_daily__enrollment_anchor_exists.sql`
- Delete:
  `src/dbt/kipptaf/tests/fct_student_enrollment_daily__no_null_entrydate_rows.sql`
- Delete:
  `src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_current_record_per_enrollment_year.sql`
- Delete:
  `src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_latest_record_per_enrollment.sql`
- Delete:
  `src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_month_end_per_enrollment_month.sql`
- Delete:
  `src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_week_end_per_enrollment_week.sql`

- [ ] **Step 1: Write the anchor-existence test**

Create `fct_student_attendance_daily__enrollment_anchor_exists.sql`:

```sql
-- Every (school, academic year) with attendance rows must have at least one
-- is_current_record = TRUE. A zero-anchor school means the point-in-time
-- enrollment headcount would read 0 for it — the non-session-day rebuild
-- failure mode cbini flagged. school is identified via dim_student_enrollments
-- (location_key); academic_year is the KIPP July-start year from date_key.
with anchored as (
    select
        d.location_key,
        if(
            extract(month from f.date_key) >= 7,
            extract(year from f.date_key),
            extract(year from f.date_key) - 1
        ) as academic_year,
        f.is_current_record,
    from {{ ref("fct_student_attendance_daily") }} as f
    inner join
        {{ ref("dim_student_enrollments") }} as d
        on f.student_enrollment_key = d.student_enrollment_key
)

select
    location_key,
    academic_year,
    countif(is_current_record) as n_current,
from anchored
group by location_key, academic_year
having countif(is_current_record) = 0
```

- [ ] **Step 2: Delete the five obsolete enrollment tests**

```bash
git rm src/dbt/kipptaf/tests/fct_student_enrollment_daily__no_null_entrydate_rows.sql \
       src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_current_record_per_enrollment_year.sql \
       src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_latest_record_per_enrollment.sql \
       src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_month_end_per_enrollment_month.sql \
       src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_week_end_per_enrollment_week.sql
```

- [ ] **Step 3: Run the new test against dev**

Run:
`uv run dbt test --select fct_student_attendance_daily --project-dir src/dbt/kipptaf --target dev`
Expected: PASS, including the new `__enrollment_anchor_exists` test (0 rows
returned — no school/year with rows lacks an anchor).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/tests/fct_student_attendance_daily__enrollment_anchor_exists.sql
git commit -m "test(dbt): enrollment anchor-existence test; remove fct_student_enrollment_daily tests"
```

---

### Task 4: Repoint the `student_enrollments` cube to the attendance fact

**Files:**

- Modify: `src/cube/model/cubes/students/student_enrollments.yml`

- [ ] **Step 1: Repoint `sql_table` and drop the direct `locations` join**

Change `sql_table` to `kipptaf_marts.fct_student_attendance_daily`. Remove the
`locations` join block (the attendance fact has no `location_key` column;
location is reached via `student_enrollment_stints`). Keep the `dates` and
`student_enrollment_stints` joins. The cube header becomes:

```yaml
cubes:
  - name: student_enrollments
    public: false
    sql_table: kipptaf_marts.fct_student_attendance_daily

    joins:
      - name: dates
        sql: "{dates.date_day} = CAST({CUBE}.date_key AS TIMESTAMP)"
        relationship: many_to_one

      # location, student identity, grade, and status are all reached via the
      # stint dim — single FK route, no diamond.
      - name: student_enrollment_stints
        sql: >
          {student_enrollment_stints.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one
```

- [ ] **Step 2: Fix the primary key and drop `location_key`**

Replace the `student_enrollment_daily_key` PK dimension with the attendance
fact's PK, and delete the `location_key` dimension:

```yaml
dimensions:
  - name: student_attendance_daily_key
    description: >-
      Surrogate key from student_number, _dbt_source_project, and calendardate.
      Primary key for the underlying attendance daily fact.
    sql: student_attendance_daily_key
    type: string
    primary_key: true

  - name: student_enrollment_key
    description: >-
      FK to student_enrollment_stints. Surrogate key from student_number,
      _dbt_source_project, academic_year, entrydate.
    sql: student_enrollment_key
    type: string
```

- [ ] **Step 3: Remap the anchor dimensions to the new fact columns**

The guard injects `student_enrollments.is_current_record` (default),
`student_enrollments.is_month_end_record` (month), and
`student_enrollments.is_week_end_record` (week). Map those dimension names to
the new per-school fact columns (note `is_month_end_record`
/`is_week_end_record` dimensions point at the `is_enrollment_*` columns):

```yaml
- name: is_current_record
  description: >-
    TRUE on the school's latest attendance day that has occurred (per school ×
    academic year, capped at today). Default point-in-time enrollment anchor.
  sql: is_current_record
  type: boolean
  public: true

- name: is_month_end_record
  description: >-
    TRUE on the school's latest attendance day of each calendar month. Use with
    month granularity for point-in-time enrollment trends.
  sql: is_enrollment_month_end_record
  type: boolean
  public: true

- name: is_week_end_record
  description: >-
    TRUE on the school's latest attendance day of each calendar week. Use with
    week granularity for point-in-time enrollment trends.
  sql: is_enrollment_week_end_record
  type: boolean
  public: true

- name: is_latest_record
  description: >-
    TRUE on the last attendance day of each enrollment stint (per
    student_enrollment_key). Per-stint "served" marker, not a period-end anchor.
  sql: is_latest_record
  type: boolean
  public: true

- name: school_week_start_date
  description: >-
    PowerSchool per-school school-week start (week_start_monday). Group the
    weekly enrollment trend by THIS, not Cube's native week granularity (which
    is ISO) — matches topline's school-week buckets. The snapshot guard injects
    the week anchor when a query groups by this dimension (Task 7).
  sql: CAST(school_week_start_date AS TIMESTAMP)
  type: time
  public: true
```

Remove the `enrollment_date`, `year_in_network`, and any other dimensions that
referenced `fct_student_enrollment_daily`-only columns not present on the
attendance fact. (`enrollment_date` can be re-added as
`CAST(date_key AS TIMESTAMP)` if a view needs it — the detail view does not
currently include it, so omit unless Task 5 needs it.)

- [ ] **Step 4: Keep the `count_students` measure unchanged**

It already reads `{student_enrollment_stints.student_key}` as `count_distinct`,
which resolves through the retained `student_enrollment_stints` join. Verify the
measure block is intact:

```yaml
measures:
  - name: count_students
    description: >-
      Distinct students enrolled, point-in-time. Counts each student once as of
      the most recent in-session school day in the query: the exact date if a
      single dates_date_day is pinned (e.g. 2025-10-01 for the fall count),
      otherwise each school's latest day in the period. Group by month or week
      to trend the headcount. Matches topline Total Enrollment (counted by
      entry/exit dates, not status). Governed by the snapshot guard so it is
      always point-in-time, never an unanchored day-sum.
    sql: "{student_enrollment_stints.student_key}"
    type: count_distinct
    public: true
```

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/cubes/students/student_enrollments.yml
git commit -m "refactor(cube): point student_enrollments at fct_student_attendance_daily"
```

---

### Task 5: Update the enrollment views (locations join path + PK member)

**Files:**

- Modify: `src/cube/model/views/students/student_enrollments_summary.yml`
- Modify: `src/cube/model/views/students/student_enrollments_detail.yml`

- [ ] **Step 1: Route locations through the stint dim in both views**

In each view, change the locations and regions `join_path` from the direct path
to the via-stint path. The last `join_path` segment stays `locations` /
`regions`, so the `prefix` and folder member names (`locations_location_name`,
`regions_region_name`, …) are unchanged.

`student_enrollments.locations` →
`student_enrollments.student_enrollment_stints.locations`
`student_enrollments.locations.regions` →
`student_enrollments.student_enrollment_stints.locations.regions`

For example, in `student_enrollments_summary.yml`:

```yaml
- join_path: student_enrollments.student_enrollment_stints.locations
  prefix: true
  includes:
    - location_name
    - abbreviation
    - grade_band
    - campus
    - city

- join_path: student_enrollments.student_enrollment_stints.locations.regions
  prefix: true
  includes:
    - region_name
    - state
```

Apply the identical join_path change in `student_enrollments_detail.yml`.

- [ ] **Step 2: Rename the PK member in the detail view**

In `student_enrollments_detail.yml`, the `student_enrollments` `includes:` lists
`student_enrollment_daily_key` — rename to `student_attendance_daily_key`
(matching the cube PK from Task 4). Update the same name in the `Enrollment`
folder `members:` list.

- [ ] **Step 3: Verify no other dropped dimensions are referenced**

Grep both views for `location_key`, `enrollment_date`, `year_in_network`,
`student_enrollment_daily_key`. Any hit must be removed or renamed — the cube no
longer exposes those (Task 4).

Run:
`rg 'location_key|enrollment_date|year_in_network|student_enrollment_daily_key' src/cube/model/views/students/`
Expected: no matches after edits (or only the renamed
`student_attendance_daily_key`).

- [ ] **Step 3b: Expose `school_week_start_date` for the weekly trend**

In both views' `student_enrollments` `includes:` list, add
`school_week_start_date` (the cube dimension from Task 4). Add it to the `Date`
folder `members:` list in each view's `meta.folders`. This is the dimension
analysts group by for the school-week enrollment trend (the guard injects the
week anchor on it — Task 7).

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/students/student_enrollments_summary.yml src/cube/model/views/students/student_enrollments_detail.yml
git commit -m "refactor(cube): enrollment views via stint dim; expose school_week_start_date"
```

---

### Task 5b: Realign the attendance cube CA weekly trend to school weeks

**Files:**

- Modify: `src/cube/model/cubes/student_attendance/student_attendance.yml`
- Modify:
  `src/cube/model/views/student_attendance/student_attendance_summary.yml`
- Modify:
  `src/cube/model/views/student_attendance/student_attendance_detail.yml`

- [ ] **Step 1: Add the `school_week_start_date` dimension to the cube**

In `student_attendance.yml` add a time dimension (the fact now outputs the
column, Task 1 Step 4):

```yaml
- name: school_week_start_date
  description: >-
    PowerSchool per-school school-week start (week_start_monday). Group the CA
    weekly trend (count_chronically_absent_week_end, pct_tier_*_week_end,
    count_truants_week_end) by THIS, not Cube's ISO week granularity — matches
    topline (int_topline__ada_running_weekly).
  sql: CAST(school_week_start_date AS TIMESTAMP)
  type: time
  public: true
```

No measure-SQL change is needed — the `_week_end` measures already filter
`{CUBE}.is_week_end_record = true`, and `is_week_end_record` is realigned to
school weeks in Task 1. The guard (Task 7) now requires the
`school_week_start_date` grouping for `_week_end` measures.

- [ ] **Step 2: Update the `is_week_end_record` dimension description**

In the cube, reword the `is_week_end_record` dimension `description:` to state
it marks the last full-membership day of each **PowerSchool school week**
(`week_start_monday`), used by grouping the weekly CA trend on
`school_week_start_date`.

- [ ] **Step 3: Expose `school_week_start_date` in the attendance views**

Add `school_week_start_date` to the `student_attendance` `includes:` in both
`student_attendance_summary.yml` and `student_attendance_detail.yml`, and to the
`Date` (or `Filter`) folder `members:`. Update the `_week_end` measure
descriptions in the views (or cube) to say "group by `school_week_start_date`"
instead of "use week granularity."

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/student_attendance/student_attendance.yml src/cube/model/views/student_attendance/student_attendance_summary.yml src/cube/model/views/student_attendance/student_attendance_detail.yml
git commit -m "refactor(cube): realign attendance CA weekly trend to school weeks"
```

---

### Task 6: Delete the old fact, fix exposure, regenerate docs

**Files:**

- Delete: `src/dbt/kipptaf/models/marts/facts/fct_student_enrollment_daily.sql`
- Delete:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_enrollment_daily.yml`
- Modify: `src/dbt/kipptaf/models/exposures/cube.yml`
- Modify: `src/cube/CLAUDE.md`
- Regenerate: `docs/reference/marts-data-models.md`

- [ ] **Step 1: Delete the old fact model + properties**

```bash
git rm src/dbt/kipptaf/models/marts/facts/fct_student_enrollment_daily.sql \
       src/dbt/kipptaf/models/marts/facts/properties/fct_student_enrollment_daily.yml
```

- [ ] **Step 2: Remove the exposure dependency**

In `src/dbt/kipptaf/models/exposures/cube.yml`, delete the
`- ref('fct_student_enrollment_daily')` line from the
`cube_semantic_layer.depends_on` list. Confirm `fct_student_attendance_daily` is
already present (it is — the `student_attendance` cube reads it).

- [ ] **Step 3: Remove the obsolete diamond note from `src/cube/CLAUDE.md`**

Delete the `student_enrollments` locations-diamond bullet under "Avoid diamond
paths" (the `student_enrollments` daily-fact cube no longer declares a direct
`locations` join, so there is no diamond). Leave the general diamond guidance
and the `student_attendance.yml → school_calendars` compound-join example
intact.

- [ ] **Step 4: Parse and confirm no dangling refs**

Run: `uv run dbt parse --project-dir src/dbt/kipptaf --target dev` Expected:
parses clean — no model `ref('fct_student_enrollment_daily')` remains.

Run: `rg "fct_student_enrollment_daily" src/` Expected: no matches (SQL, YAML,
or cube).

- [ ] **Step 5: Regenerate the marts reference doc**

Run: `uv run python src/teamster/.../generate_marts_reference.py` (the generator
used by `docs/reference/marts-data-models.md` — locate via
`rg -l "marts-data-models" scripts/ src/`). Expected: the regenerated doc drops
the `fct_student_enrollment_daily` section and adds the three new anchor columns
under `fct_student_attendance_daily`.

- [ ] **Step 6: Commit**

```bash
git add -u
git add docs/reference/marts-data-models.md
git commit -m "refactor(dbt): delete fct_student_enrollment_daily; regenerate marts reference"
```

---

### Task 7: `cube.js` — drive the week period off the school-week grouping

**Files:**

- Modify: `src/cube/cube.js`

**Why:** Cube's native `granularity: "week"` is ISO Monday — it cannot express a
PowerSchool school week. The anchors are school-week (`week_start_monday`), so
the snapshot guard must drive its "week" period off a query grouping by
`school_week_start_date`, not Cube's ISO week. This applies to BOTH snapshot
cubes (`student_attendance` CA `_week_end` family and `student_enrollments`
`count_students`). `SNAPSHOT_CUBES` / `SNAPSHOT_MEASURE_STEMS` /
`SNAPSHOT_ANCHOR_OVERRIDES` membership is already correct — only the granularity
resolution inside the `for (const cubePrefix of SNAPSHOT_CUBES)` loop changes
(`cube.js` ~lines 218-309).

- [ ] **Step 1: Detect the school-week grouping**

Inside the loop, after computing `dateDayTd` / `granularity`, add:

```js
const groupsBySchoolWeek = [
  ...(query.dimensions ?? []),
  ...(query.timeDimensions ?? []).map((td) => td.dimension),
].some((m) => m?.endsWith("school_week_start_date"));

// School weeks replace Cube's ISO week for snapshot measures: the anchors
// are week_start_monday-based, so weekly trends MUST group by
// school_week_start_date. Treat that grouping as the "week" period.
const period = groupsBySchoolWeek ? "week" : granularity;
```

- [ ] **Step 2: Reject ISO `granularity: "week"` for snapshot measures**

Where the guard currently validates granularity, throw if a snapshot week is
requested via Cube's ISO granularity instead of the school-week dimension:

```js
if (granularity === "week" && !groupsBySchoolWeek) {
  throw new Error(
    `Weekly snapshot trends use school weeks — group by ` +
      `<cube>.school_week_start_date, not Cube's granularity: "week" ` +
      `(which is ISO Monday and does not match PowerSchool school weeks).`,
  );
}
```

- [ ] **Step 3: Key the `_week_end` requirement on the school-week grouping**

Change the `_week_end` named-measure check from "requires granularity week" to
"requires `groupsBySchoolWeek`" (keep `_month_end` → `granularity === "month"`):

```js
for (const [suffix, ok, hint] of [
  ["_month_end", granularity === "month", 'granularity: "month"'],
  ["_week_end", groupsBySchoolWeek, "school_week_start_date grouping"],
]) {
  if (measures.some((m) => m.endsWith(suffix)) && !ok) {
    throw new Error(`${suffix} measures must be grouped by ${hint}.`);
  }
}
```

- [ ] **Step 4: Resolve the anchor off `period`, not `granularity`**

Replace the `granularity`-keyed anchor selection with `period`:

```js
      if (period === "day") continue;

      const anchorMap = {
        ...SNAPSHOT_ANCHOR_DIMENSIONS,
        ...(SNAPSHOT_ANCHOR_OVERRIDES[cubePrefix] ?? {}),
      };
      const anchorDimension = anchorMap[period] ?? anchorMap.default;
```

The unsupported-granularity throw (currently rejecting non day/week/month) keeps
using `granularity` for the ISO `day`/`month` paths; ensure a bare
school-week-grouped query (no `dates_date_day` granularity) falls through
cleanly to `period === "week"`.

- [ ] **Step 5: Update the `SNAPSHOT_MEASURE_STEMS` comment**

Reword the `student_enrollments` note: "count_students is
count_distinct(student_key) over the attendance daily fact; a student enrolled
across N in-session days appears in N rows, so an unanchored count overcounts —
it needs the guard. Weekly trends group by school_week_start_date." Note that
both cubes' week anchors are now school-week-based.

- [ ] **Step 6: Trunk + commit**

Run: `/workspaces/teamster/.trunk/tools/trunk check --force src/cube/cube.js`

```bash
git add src/cube/cube.js
git commit -m "feat(cube): drive snapshot week anchor off school-week grouping"
```

Validation of this rework happens against Cube Dev Mode in Task 8 (both the
enrollment weekly trend and the attendance CA `_week_end` measures must compile
and return sane numbers when grouped by `school_week_start_date`, and must throw
the helpful error when a snapshot week measure is requested with ISO
`granularity: "week"`).

---

### Task 8: Full build, Cube Dev Mode validation, final reconciliation

**Files:** none (validation + handoff)

- [ ] **Step 1: Full downstream dbt build**

Run:
`uv run dbt build --select fct_student_attendance_daily+ --project-dir src/dbt/kipptaf --target dev`
Expected: PASS — model + all tests (incl. the new anchor-existence test) +
downstream consumers. Note: this is a dev build; `--target prod` is hand-off
only.

- [ ] **Step 2: Trunk check all touched files**

Run from repo root:
`/workspaces/teamster/.trunk/tools/trunk check --force <every touched .sql/.yml/.js/.md>`
Expected: no findings.

- [ ] **Step 3: Cube Dev Mode validation**

Per `src/cube/CLAUDE.md` "Testing Cube measures backed by new dbt columns":
temporarily point the `student_enrollments` cube `sql_table` at
`zz_<username>_kipptaf_marts.fct_student_attendance_daily`, push to a Cube Cloud
Dev Mode branch, and confirm through `student_enrollments_summary`:

- `count_students` by `dates_academic_year` (year default → is_current_record).
- `count_students` by month (`granularity: "month"` → is_enrollment_month_end).
- `count_students` by `school_week_start_date` (school-week trend →
  is_enrollment_week_end). Confirm requesting it with Cube `granularity: "week"`
  throws the helpful "group by school_week_start_date" error (Task 7).
- `count_students` pinned to `dates_date_day = 2025-10-01` → 10,637.
- A Paterson-region filter returns a non-zero headcount. Then **revert
  `sql_table`** to `kipptaf_marts.fct_student_attendance_daily` before final
  commit.

- [ ] **Step 4: Confirm the attendance cube — regression + CA week realignment**

Through `student_attendance_summary`: `avg_daily_attendance`,
`count_chronically_absent` (with is_latest_record), and `count_students` still
resolve (per-stint daily/year anchors unchanged). Network ADA AY2025 now
includes Paterson's real (low, #4193-tracked) values — expected. Then validate
the CA weekly realignment: `count_chronically_absent_week_end` grouped by
`school_week_start_date` compiles and returns sane numbers, and **quantify the
shift** vs the prior ISO-week behavior (query the dev fact: distinct students by
old `date_trunc(week(monday))` bucket vs new `school_week_start_date` bucket for
a sample school/month) so the PR can state the magnitude on split weeks.

- [ ] **Step 5: Final commit + push for dbt Cloud CI**

```bash
git push
```

Then follow the PR through dbt Cloud CI (check terminal state before any
re-push; pull warnings with `warning_only=true` after green) per project
CLAUDE.md. Update the PR description to reflect the pivot (enrollment now rides
the attendance fact; `fct_student_enrollment_daily` removed; Paterson handled
via #4193, not in-model).

---

## Self-review notes

- **Spec coverage:** removes Paterson special-casing (Tasks 1-2); shared-spine
  enrollment on the attendance fact (Tasks 1, 4-5); cbini's non-session-day
  zero-out addressed structurally + anchor-existence test (Tasks 1, 3); separate
  cube + views (Tasks 4-5); school-week anchors for both cubes + topline
  consistency (Tasks 1, 4, 5, 5b); CA weekly realignment (Task 5b); guard rework
  for school-week grouping (Task 7); deletes the second fact (Task 6).
- **Type consistency:** new fact columns `is_current_record`,
  `is_enrollment_month_end_record`, `is_enrollment_week_end_record` (all
  boolean) are referenced identically in the SQL (Task 1), properties (Task 2),
  and cube dimensions (Task 4). The cube dimensions named `is_month_end_record`
  / `is_week_end_record` deliberately map to the `is_enrollment_*` columns so
  the guard's fixed anchor-dimension names resolve per-cube.
- **Open verification:** Step 5 of Task 6 — confirm the exact generator path for
  `marts-data-models.md` before running (it is referenced by the
  `2026-06-04-marts-data-models-reference.md` plan).
