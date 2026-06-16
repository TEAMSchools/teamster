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
- **Anchor semantics (the core design):**
  - `is_current_record` — per (school, source project, academic year), TRUE on
    the school's latest attendance day. Drives the default headcount. Excludes
    withdrawn students (their rows never equal the school's max date) and
    includes currently-enrolled students. NEW column.
  - `is_enrollment_month_end_record` / `is_enrollment_week_end_record` — same,
    partitioned additionally by month / ISO week. NEW columns. Named distinctly
    so they do not collide with the fact's existing per-stint, membership-based
    `is_month_end_record` / `is_week_end_record` (which serve the
    CA/tier/truancy measures and stay untouched).
  - The attendance fact is already capped at `current_date` at source
    (`int_powerschool__ps_adaadm_daily_ctod` has no future rows), so
    `max(date_key) over (...)` always lands on a real row — this is how cbini's
    "point-in-time count reads 0 on a non-session-day rebuild" bug is
    structurally avoided. No `least(..., current_date)` is needed.
- **Cube wiring already in place:** `cube.js` already lists
  `student_enrollments` in `SNAPSHOT_CUBES`, maps
  `SNAPSHOT_MEASURE_STEMS.student_enrollments = ["count_students"]`, and sets
  `SNAPSHOT_ANCHOR_OVERRIDES.student_enrollments = { default: "is_current_record" }`.
  No `cube.js` logic change is required — only a comment update (Task 7).

## File map

| File                                                                               | Action                                                                                                                              |
| ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql`              | Modify — remove Paterson null-out; add 3 per-school enrollment anchor columns                                                       |
| `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_daily.yml`   | Modify — add 3 anchor columns; strip "Null for Paterson…" sentences                                                                 |
| `src/dbt/kipptaf/tests/fct_student_attendance_daily__enrollment_anchor_exists.sql` | Create — anchor-existence test (cbini)                                                                                              |
| `src/dbt/kipptaf/models/marts/facts/fct_student_enrollment_daily.sql`              | Delete                                                                                                                              |
| `src/dbt/kipptaf/models/marts/facts/properties/fct_student_enrollment_daily.yml`   | Delete                                                                                                                              |
| `src/dbt/kipptaf/tests/fct_student_enrollment_daily__*.sql` (5 files)              | Delete                                                                                                                              |
| `src/cube/model/cubes/students/student_enrollments.yml`                            | Modify — repoint `sql_table`; drop direct `locations` join + `location_key`; remap anchor dims; PK → `student_attendance_daily_key` |
| `src/cube/model/views/students/student_enrollments_summary.yml`                    | Modify — locations `join_path` via stints                                                                                           |
| `src/cube/model/views/students/student_enrollments_detail.yml`                     | Modify — locations `join_path` via stints; PK member rename                                                                         |
| `src/cube/cube.js`                                                                 | Modify — comment only (stems comment references the old fact)                                                                       |
| `src/cube/CLAUDE.md`                                                               | Modify — remove the now-obsolete `student_enrollments` locations-diamond note                                                       |
| `src/dbt/kipptaf/models/exposures/cube.yml`                                        | Modify — remove `fct_student_enrollment_daily` from `depends_on`                                                                    |
| `docs/reference/marts-data-models.md`                                              | Regenerate                                                                                                                          |

Keep `student_enrollment_stints` (the `dim_student_enrollments` cube rename) —
it is still the join target for `student_key`/location/status and is unaffected.

---

### Task 1: Attendance fact — remove Paterson null-out + add per-school enrollment anchors

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql`

- [ ] **Step 1: Carry the partition columns into the `daily` CTE**

In the `daily` CTE's SELECT, add these three plain refs from the `ada` alias
(they are plumbing — used only by the window functions in the final SELECT, not
output). Place them with the other `ada.` refs, immediately after the
`student_enrollment_key` surrogate-key block:

```sql
            ada.schoolid,
            ada._dbt_source_project,
            ada.academic_year,
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

- [ ] **Step 3: Add the per-school enrollment anchors to the final SELECT**

After the existing `is_week_end_record` window expression (the last column,
before `from running`), append:

```sql
    date_key = max(date_key) over (
        partition by schoolid, _dbt_source_project, academic_year
    ) as is_current_record,

    date_key = max(date_key) over (
        partition by
            schoolid, _dbt_source_project, academic_year, date_trunc(date_key, month)
    ) as is_enrollment_month_end_record,

    date_key = max(date_key) over (
        partition by
            schoolid,
            _dbt_source_project,
            academic_year,
            -- trunk-ignore(sqlfluff/LT01): week(monday) special syntax
            date_trunc(date_key, week(monday))
    ) as is_enrollment_week_end_record,
```

Columns read bare (no alias) because the final SELECT reads from a single CTE
(`running`) — matches the existing `is_latest_record` / `is_month_end_record`
style in this model.

- [ ] **Step 4: Build the model in dev**

Run:
`uv run dbt run --select fct_student_attendance_daily --project-dir src/dbt/kipptaf --target dev`
Expected: success, creating
`zz_<username>_kipptaf_marts.fct_student_attendance_daily`.

- [ ] **Step 5: Reconcile the as-of-now and Oct-1 headcounts (incl. Paterson)**

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

- [ ] **Step 6: Run trunk on the SQL file**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql`
(run with cwd at the repo root). Expected: no findings. Fix any sqlfluff ST06
column-ordering complaints by grouping the new plain refs per the existing
layout.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql
git commit -m "feat(dbt): per-school enrollment anchors on fct_student_attendance_daily; drop Paterson null-out"
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
    TRUE on the school's latest attendance day of each calendar week
    (Monday–Sunday), FALSE otherwise. Computed per school, source project,
    academic year, and ISO week. Use with a week-granularity date dimension for
    week-over-week point-in-time enrollment trends. Correctly handles shortened
    weeks. Independent of is_week_end_record.
```

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
parses clean (the 3 new boolean columns match the SQL output).

- [ ] **Step 4: Build with contract enforcement**

Run:
`uv run dbt run --select fct_student_attendance_daily --project-dir src/dbt/kipptaf --target dev`
Expected: success (contract accepts the 3 new boolean columns).

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

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/students/student_enrollments_summary.yml src/cube/model/views/students/student_enrollments_detail.yml
git commit -m "refactor(cube): enrollment views reach locations via stint dim"
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

### Task 7: `cube.js` comment update (no logic change)

**Files:**

- Modify: `src/cube/cube.js`

- [ ] **Step 1: Confirm no logic change is needed**

`SNAPSHOT_CUBES`, `SNAPSHOT_MEASURE_STEMS.student_enrollments`, and
`SNAPSHOT_ANCHOR_OVERRIDES.student_enrollments` are already correct for the
repointed cube (the cube name and measure name are unchanged). Do not edit the
logic.

- [ ] **Step 2: Update the stems comment if it names the old fact**

If the `SNAPSHOT_MEASURE_STEMS` comment block (lines ~59-72) describes
`student_enrollments` as reading a dedicated daily enrollment fact, reword to:
"student_enrollments: count_students is count_distinct(student_key) over the
attendance daily fact; a student enrolled across N in-session days appears in N
rows, so an unanchored count over a range overcounts — it needs the guard."

- [ ] **Step 3: Commit (skip if no change)**

cube.js is not a protected hook file, but verify trunk: Run:
`/workspaces/teamster/.trunk/tools/trunk check --force src/cube/cube.js`

```bash
git add src/cube/cube.js
git commit -m "docs(cube): update snapshot-stems comment for attendance-fact-backed enrollment"
```

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
- `count_students` by week and by month (trend → is*enrollment*\*\_end_record).
- `count_students` pinned to `dates_date_day = 2025-10-01` → 10,637.
- A Paterson-region filter returns a non-zero headcount. Then **revert
  `sql_table`** to `kipptaf_marts.fct_student_attendance_daily` before final
  commit.

- [ ] **Step 4: Confirm the attendance regression is intact**

Through `student_attendance_summary`, confirm `avg_daily_attendance`,
`count_chronically_absent` (with is_latest_record), and `count_students` still
resolve — the existing per-stint anchors and measures are unchanged. Network ADA
AY2025 now includes Paterson's real (low, #4193-tracked) values — expected.

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
  cube + views (Tasks 4-5); deletes the second fact (Task 6).
- **Type consistency:** new fact columns `is_current_record`,
  `is_enrollment_month_end_record`, `is_enrollment_week_end_record` (all
  boolean) are referenced identically in the SQL (Task 1), properties (Task 2),
  and cube dimensions (Task 4). The cube dimensions named `is_month_end_record`
  / `is_week_end_record` deliberately map to the `is_enrollment_*` columns so
  the guard's fixed anchor-dimension names resolve per-cube.
- **Open verification:** Step 5 of Task 6 — confirm the exact generator path for
  `marts-data-models.md` before running (it is referenced by the
  `2026-06-04-marts-data-models-reference.md` plan).
