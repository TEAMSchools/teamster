> **Measures: not implemented in this pass.** Skip all `measures:` sections when
> writing cube files — dimensions, joins, and `public: false` only. Remove
> measure names from view `includes:` lists (keep dimension names only). Add
> measures on demand as analysts request specific aggregations.

# Cube Attendance Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new attendance fact cubes (`student_attendance_interventions`,
`student_attendance_streaks`) and four consumer views
(`student_attendance_interventions_detail`,
`student_attendance_interventions_summary`, `student_attendance_streaks_detail`,
`student_attendance_streaks_summary`) to the Cube semantic layer.

**Architecture:** Both cubes map to existing `kipptaf_marts` fact tables. The
interventions cube inlines `dim_student_attendance_intervention_types` via
`sql:` (no independent analytical grain). The streaks cube uses role-playing
date FKs (`streak_start_date_key`, `streak_end_date_key`) — only
`streak_start_date_key` is joined to `dates` (the primary time dimension); the
end date is exposed as a raw dimension cast to TIMESTAMP. Both cubes join
`student_enrollments` for location / region / student traversal. Both start with
`student_` and are automatically gated by `isStudentMember` in `cube.js` — no
`cube.js` changes required.

**Prerequisite:** Plan 0 (`2026-06-01-cube-model-yaml-implementation.md`) must
be complete. All conformed cubes use bare business names (`dates`, `locations`,
`regions`, `terms`, `school_calendars`); the attendance fact cube is named
`student_attendance`. All views use `student_attendance_detail` /
`student_attendance_summary`.

**Tech Stack:** Cube YAML (`src/cube/model/`), Python (`pytest`, `pyyaml`)

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

---

## Source model reference

### `fct_student_attendance_interventions`

Grain: one row per student × intervention type × academic year. Key columns:

| Column                                | Type    | Notes                                                              |
| ------------------------------------- | ------- | ------------------------------------------------------------------ |
| `student_attendance_intervention_key` | string  | PK — surrogate from student_number, academic_year, comm log reason |
| `student_enrollment_key`              | string  | FK → dim_student_enrollments                                       |
| `intervention_type_key`               | string  | FK → dim_student_attendance_intervention_types (inlined)           |
| `family_communication_key`            | string  | FK → fct_family_communications (nullable — no Cube join needed)    |
| `date_key`                            | date    | FK → dim_dates. Null when intervention not yet completed           |
| `academic_year`                       | int64   | KIPP AY (July start)                                               |
| `absence_threshold`                   | int64   | Unexcused absences that triggered the intervention                 |
| `days_absent_unexcused`               | float64 | YTD unexcused absence count at evaluation time                     |
| `has_communication_log`               | boolean | TRUE if a matching comm log was found                              |
| `is_chronic_absence_exception`        | boolean | TRUE if student is in Attendance Exceptions program                |

No `contains_pii: true` columns in either the fact or the inlined dim — no PII
excludes needed.

### `dim_student_attendance_intervention_types` (inlined into interventions cube)

Grain: one row per region × intervention threshold. Columns to expose:

| Column                        | Type   | Notes                                                 |
| ----------------------------- | ------ | ----------------------------------------------------- |
| `intervention_type_key`       | string | PK — join key used to inline                          |
| `region_key`                  | string | FK → dim_regions                                      |
| `family_communication_reason` | string | DeansList comm log reason (e.g. 'Chronic Absence: 4') |
| `absence_threshold`           | int64  | Threshold that triggers this intervention type        |

`absence_threshold` appears on both tables; use the fact's value (degenerate dim
column vs FK attribute — the fact already carries it, inline dim value would
duplicate). Expose `family_communication_reason` from the inlined dim as a
grouping dimension.

### `fct_student_attendance_streaks`

Grain: one row per student × consecutive attendance streak. Key columns:

| Column                          | Type   | Notes                                                                            |
| ------------------------------- | ------ | -------------------------------------------------------------------------------- |
| `student_attendance_streak_key` | string | PK — surrogate from streak_id, \_dbt_source_project                              |
| `student_enrollment_key`        | string | FK → dim_student_enrollments                                                     |
| `streak_start_date_key`         | date   | FK → dim_dates (primary time dim)                                                |
| `streak_end_date_key`           | date   | FK → dim_dates (role-playing; exposed as raw dimension, not a second dates join) |
| `academic_year`                 | int64  | KIPP AY (July start)                                                             |
| `attendance_code`               | string | Attendance code repeated across the streak                                       |
| `streak_length_membership`      | int64  | Membership days in streak                                                        |
| `streak_length_calendar`        | int64  | Calendar days in streak                                                          |

No `contains_pii: true` columns — no PII excludes needed.

**Role-playing date FKs:** The streaks fact has two date FKs
(`streak_start_date_key`, `streak_end_date_key`). Cube does not allow two joins
to the same cube name. Join only `streak_start_date_key` → `dates` (the primary
time dimension for filtering and trend analysis). Expose `streak_end_date_key`
as a plain `type: time` dimension via `CAST(streak_end_date_key AS TIMESTAMP)`
directly in the cube — no second `dates` join required.

---

## Task 1: `student_attendance_interventions` cube

The fact table references `dim_student_attendance_intervention_types` as a
lookup-only dim with no independent analytical grain, so it is inlined into the
cube `sql:` block (see spec Design Decision: "One cube per analytical grain").
`date_key` is nullable (null when the intervention has not been completed), so
the `dates` join is LEFT JOIN. `student_enrollment_key` is non-null so
`student_enrollments` is INNER (the default `many_to_one` relationship).

**Files:**

- Create: `src/cube/model/cubes/attendance/student_attendance_interventions.yml`

- [ ] **Step 1: Write the cube file**

```yaml
cubes:
  - name: student_attendance_interventions
    public: false
    # dim_student_attendance_intervention_types is a lookup dim with no
    # independent analytical grain — inlined here via sql: per spec convention.
    sql: |
      SELECT
        f.student_attendance_intervention_key,
        f.student_enrollment_key,
        f.family_communication_key,
        f.date_key,
        f.academic_year,
        f.absence_threshold,
        f.days_absent_unexcused,
        f.has_communication_log,
        f.is_chronic_absence_exception,
        it.family_communication_reason,
        it.region_key AS intervention_region_key
      FROM kipptaf_marts.fct_student_attendance_interventions f
      LEFT JOIN kipptaf_marts.dim_student_attendance_intervention_types it
        ON it.intervention_type_key = f.intervention_type_key

    joins:
      # date_key is nullable (null when intervention not yet completed) — LEFT JOIN
      - name: dates
        sql: "{dates.date_day} = CAST({CUBE}.date_key AS TIMESTAMP)"
        relationship: many_to_one

      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

    dimensions:
      - name: student_attendance_intervention_key
        sql: student_attendance_intervention_key
        type: string
        primary_key: true

      - name: intervention_date
        description: >-
          Date the communication was logged. Null when the intervention has not
          yet been completed (has_communication_log = false).
        sql: CAST(date_key AS TIMESTAMP)
        type: time
        public: true

      - name: academic_year
        description:
          KIPP academic year (July start) for this intervention record.
        sql: academic_year
        type: number
        public: true

      - name: absence_threshold
        description: >-
          Number of unexcused absences that triggered this intervention type.
          Thresholds differ by region — Miami: 3, 5, 8, 10, 15+; Newark/Camden:
          4, 8, 12, 16, 20, 30, 40.
        sql: absence_threshold
        type: number
        public: true

      - name: days_absent_unexcused
        description: >-
          Student's year-to-date unexcused absence count at the time of
          evaluation.
        sql: days_absent_unexcused
        type: number
        public: true

      - name: has_communication_log
        description: >-
          TRUE if the expected intervention was matched against a communication
          log record, FALSE if no matching record was found. Existence check —
          absence of a log can reflect either a skipped intervention or a
          logging gap.
        sql: has_communication_log
        type: boolean
        public: true

      - name: is_chronic_absence_exception
        description: >-
          TRUE if the student is enrolled in the Attendance Exceptions special
          program, exempting them from chronic absence tracking.
        sql: is_chronic_absence_exception
        type: boolean
        public: true

      - name: family_communication_reason
        description: >-
          DeansList comm log reason value that identifies the intervention type
          (e.g., 'Chronic Absence: 4'). Sourced from the inlined intervention
          types dimension.
        sql: family_communication_reason
        type: string
        public: true

      - name: count_completed_interventions
        description: Interventions where a matching communication log was found.
        sql: student_attendance_intervention_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.has_communication_log = true"

      - name: count_missing_interventions
        description:
          Interventions where no matching communication log was found.
        sql: student_attendance_intervention_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.has_communication_log = false"

      - name: pct_interventions_completed
        description: >-
          Percentage of required interventions that have a matching
          communication log.
        sql: >-
          1.0 * {count_completed_interventions} / NULLIF({count_interventions},
          0)
        type: number
        format: percent
        public: true

      - name: count_students_with_intervention
        description: Distinct students with at least one intervention record.
        sql: student_enrollment_key
        type: count_distinct
        public: true

      - name: avg_days_absent_unexcused
        description: Average YTD unexcused absence count at evaluation time.
        sql: days_absent_unexcused
        type: avg
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/attendance/student_attendance_interventions.yml').read_text())
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube['public'])
print('joins:', [j['name'] for j in cube['joins']])
dims = [d['name'] for d in cube['dimensions']]
measures = [m['name'] for m in cube['measures']]
print('dimensions:', dims)
print('measures:', measures)
"
```

Expected output:

```text
cube name: student_attendance_interventions
public: False
joins: ['dates', 'student_enrollments']
dimensions: ['student_attendance_intervention_key', 'intervention_date', 'academic_year', 'absence_threshold', 'days_absent_unexcused', 'has_communication_log', 'is_chronic_absence_exception', 'family_communication_reason']
measures: ['count_interventions', 'count_completed_interventions', 'count_missing_interventions', 'pct_interventions_completed', 'count_students_with_intervention', 'avg_days_absent_unexcused']
```

- [ ] **Step 3: Run schema test**

```bash
uv run pytest tests/cube/test_cube_schema.py -v -k "interventions"
```

Expected: PASS (cube name does not start with `dim_` or `fct_`).

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/attendance/student_attendance_interventions.yml
git commit -m "feat(cube): add student_attendance_interventions cube with inlined intervention types dim"
```

---

## Task 2: `student_attendance_streaks` cube

The streaks fact has two role-playing date FKs. Only `streak_start_date_key`
joins the `dates` cube (primary time dimension for trend analysis and Cube time
filters). `streak_end_date_key` is exposed as a raw `type: time` dimension via
`CAST`. No second `dates` join is declared — Cube would require a distinct cube
name for a second join to the same cube, and there is no analytical need for a
second dates hop here.

**Files:**

- Create: `src/cube/model/cubes/attendance/student_attendance_streaks.yml`

- [ ] **Step 1: Write the cube file**

```yaml
cubes:
  - name: student_attendance_streaks
    public: false
    sql_table: kipptaf_marts.fct_student_attendance_streaks

    joins:
      # Join on streak_start_date_key — the primary time dimension.
      # streak_end_date_key is exposed as a raw dimension (CAST to TIMESTAMP)
      # rather than a second dates join — Cube does not allow two joins to the
      # same cube name.
      - name: dates
        sql:
          "{dates.date_day} = CAST({CUBE}.streak_start_date_key AS TIMESTAMP)"
        relationship: many_to_one

      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

    dimensions:
      - name: student_attendance_streak_key
        sql: student_attendance_streak_key
        type: string
        primary_key: true

      - name: streak_start_date
        description: First date of the streak.
        sql: CAST(streak_start_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: streak_end_date
        description: Last date of the streak.
        sql: CAST(streak_end_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: academic_year
        description: KIPP academic year (July start) derived from yearid + 1990.
        sql: academic_year
        type: number
        public: true

      - name: attendance_code
        description: Attendance code repeated across all days of this streak.
        sql: attendance_code
        type: string
        public: true

      - name: streak_length_membership
        description: Number of membership days (school days) in the streak.
        sql: streak_length_membership
        type: number
        public: true

      - name: streak_length_calendar
        description: >-
          Number of calendar days in the streak (end_date - start_date + 1),
          including weekends and holidays.
        sql: streak_length_calendar
        type: number
        public: true

      - name: count_students_with_streaks
        description: Distinct students with at least one streak record.
        sql: student_enrollment_key
        type: count_distinct
        public: true

      - name: avg_streak_length_membership
        description: Average streak length in membership days.
        sql: streak_length_membership
        type: avg
        public: true

      - name: avg_streak_length_calendar
        description: Average streak length in calendar days.
        sql: streak_length_calendar
        type: avg
        public: true

      - name: max_streak_length_membership
        description:
          Longest streak in membership days within the filtered period.
        sql: streak_length_membership
        type: max
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/attendance/student_attendance_streaks.yml').read_text())
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube['public'])
print('sql_table:', cube['sql_table'])
print('joins:', [j['name'] for j in cube['joins']])
dims = [d['name'] for d in cube['dimensions']]
measures = [m['name'] for m in cube['measures']]
print('dimensions:', dims)
print('measures:', measures)
"
```

Expected output:

```text
cube name: student_attendance_streaks
public: False
sql_table: kipptaf_marts.fct_student_attendance_streaks
joins: ['dates', 'student_enrollments']
dimensions: ['student_attendance_streak_key', 'streak_start_date', 'streak_end_date', 'academic_year', 'attendance_code', 'streak_length_membership', 'streak_length_calendar']
measures: ['count_streaks', 'count_students_with_streaks', 'avg_streak_length_membership', 'avg_streak_length_calendar', 'max_streak_length_membership']
```

- [ ] **Step 3: Run schema test**

```bash
uv run pytest tests/cube/test_cube_schema.py -v -k "streaks"
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/attendance/student_attendance_streaks.yml
git commit -m "feat(cube): add student_attendance_streaks cube; role-playing end-date as raw dimension"
```

---

## Task 3: `student_attendance_interventions_detail` view

Detail view: exposes individual intervention records with enrollment-level
context and student identity. Student PII fields (full name, identifiers) are
included but gated by `cube-access-student-pii` — intervention coordinators
doing follow-up need to see which student they're acting on. Access policy
follows the standard student Pattern 1: `detail-access` excludes PII fields;
`cube-access-student-pii` restores full access.

**Note on `prefix: true`:** `join_path: student_attendance_interventions.dates`
with `prefix: true` produces member names prefixed `dates_*`. The
`student_enrollments` join path produces `student_enrollments_*` prefixed
members. All `meta.folders` entries must use the post-prefix names.

**Files:**

- Create:
  `src/cube/model/views/attendance/student_attendance_interventions_detail.yml`

- [ ] **Step 1: Write the view file**

```yaml
views:
  - name: student_attendance_interventions_detail
    description: >-
      Row-level student attendance intervention records. One row per student x
      intervention type x academic year. Tracks whether each required
      communication intervention was completed based on the student's unexcused
      absence count exceeding the regional threshold. Intervention types are
      inlined — family_communication_reason identifies the specific threshold
      bucket. date_key (exposed as intervention_date) is null when no matching
      communication log exists (has_communication_log = false). Use
      pct_interventions_completed for completion rate roll-ups; filter by
      absence_threshold to focus on a specific intervention tier.

    cubes:
      - join_path: student_attendance_interventions
        includes:
          - count_interventions
          - count_completed_interventions
          - count_missing_interventions
          - pct_interventions_completed
          - count_students_with_intervention
          - avg_days_absent_unexcused
          - intervention_date
          - academic_year
          - absence_threshold
          - days_absent_unexcused
          - has_communication_log
          - is_chronic_absence_exception
          - family_communication_reason

      - join_path: student_attendance_interventions.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - academic_year

      - join_path: student_attendance_interventions.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_attendance_interventions.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_attendance_interventions.student_enrollments
        prefix: true
        includes:
          - student_enrollment_key
          - grade_level
          - graduation_year

      - join_path: student_attendance_interventions.student_enrollments.students
        prefix: true
        includes:
          - student_key
          - full_name
          - birth_date
          - lea_student_identifier
          - state_student_identifier
          - gender_identity
          - race
          - enrollment_status

    meta:
      folders:
        - name: Intervention
          members:
            - intervention_date
            - academic_year
            - absence_threshold
            - days_absent_unexcused
            - has_communication_log
            - is_chronic_absence_exception
            - family_communication_reason
        - name: Date
          members:
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_academic_year
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - locations_campus
            - locations_city
            - regions_region_name
            - regions_state
        - name: Student
          members:
            - students_student_key
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
            - students_gender_identity
            - students_race
            - students_enrollment_status
        - name: Enrollment
          members:
            - student_enrollments_student_enrollment_key
            - student_enrollments_grade_level
            - student_enrollments_graduation_year

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
      - group: cube-access-student-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/attendance/student_attendance_interventions_detail.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
folder_names = [f['name'] for f in view['meta']['folders']]
print('folders:', folder_names)
"
```

Expected output:

```text
view name: student_attendance_interventions_detail
join paths: ['student_attendance_interventions', 'student_attendance_interventions.dates', 'student_attendance_interventions.student_enrollments.locations', 'student_attendance_interventions.student_enrollments.locations.regions', 'student_attendance_interventions.student_enrollments', 'student_attendance_interventions.student_enrollments.students']
access groups: ['detail-access', 'cube-access-student-pii']
folders: ['Intervention', 'Date', 'Location', 'Student', 'Enrollment']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/views/attendance/student_attendance_interventions_detail.yml
git commit -m "feat(cube): add student_attendance_interventions_detail view"
```

---

## Task 4: `student_attendance_interventions_summary` view

Summary view: aggregate-safe dimensions and measures only. No individual
identifiers (no `student_enrollment_key`, no `student_key`). `date_day` from the
dates join is included for trend analysis. Access policy: single
`summary-access` block.

**Files:**

- Create:
  `src/cube/model/views/attendance/student_attendance_interventions_summary.yml`

- [ ] **Step 1: Write the view file**

```yaml
views:
  - name: student_attendance_interventions_summary
    description: >-
      Aggregated student attendance intervention completion rates. Use for
      school/region roll-ups of pct_interventions_completed by absence threshold
      tier, academic year, or demographic breakdown. No individual student
      identifiers — filter by has_communication_log and group by
      family_communication_reason or absence_threshold to analyze completion by
      intervention type.

    cubes:
      - join_path: student_attendance_interventions
        includes:
          - count_interventions
          - count_completed_interventions
          - count_missing_interventions
          - pct_interventions_completed
          - count_students_with_intervention
          - avg_days_absent_unexcused
          - academic_year
          - absence_threshold
          - has_communication_log
          - is_chronic_absence_exception
          - family_communication_reason

      - join_path: student_attendance_interventions.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - academic_year

      - join_path: student_attendance_interventions.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_attendance_interventions.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_attendance_interventions.student_enrollments
        prefix: true
        includes:
          - grade_level
          - graduation_year

      - join_path: student_attendance_interventions.student_enrollments.students
        prefix: true
        includes:
          - gender_identity
          - race

    meta:
      folders:
        - name: Intervention
          members:
            - academic_year
            - absence_threshold
            - has_communication_log
            - is_chronic_absence_exception
            - family_communication_reason
        - name: Date
          members:
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_academic_year
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - locations_campus
            - locations_city
            - regions_region_name
            - regions_state
        - name: Student
          members:
            - students_gender_identity
            - students_race
        - name: Enrollment
          members:
            - student_enrollments_grade_level
            - student_enrollments_graduation_year

    access_policy:
      # No direct student identifiers — demographic dimensions are aggregate
      # breakdowns only.
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/attendance/student_attendance_interventions_summary.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_attendance_interventions_summary
join paths: ['student_attendance_interventions', 'student_attendance_interventions.dates', 'student_attendance_interventions.student_enrollments.locations', 'student_attendance_interventions.student_enrollments.locations.regions', 'student_attendance_interventions.student_enrollments', 'student_attendance_interventions.student_enrollments.students']
access groups: ['summary-access']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/views/attendance/student_attendance_interventions_summary.yml
git commit -m "feat(cube): add student_attendance_interventions_summary view"
```

---

## Task 5: `student_attendance_streaks_detail` view

Detail view for streaks. The `dates` join anchors on `streak_start_date_key` —
that join path provides month/year breakdown for trend analysis.
`streak_end_date` is included directly from the streaks cube (not from a dates
join). Student PII fields (name, identifiers) are included and gated by
`cube-access-student-pii` — staff investigating long absence streaks need to
identify which student they're looking at. Access policy follows student
Pattern 1.

**Note on `dates_academic_year`:** The `dates` cube exposes `academic_year` as a
member. With `prefix: true`, it becomes `dates_academic_year`. The streaks cube
also exposes its own `academic_year` (degenerate on the fact). Both are included
but serve different purposes: `dates_academic_year` comes from `dim_dates`
(calendar-based); `academic_year` from the fact row (KIPP AY from
`yearid + 1990`). They should agree for any given streak but are both exposed
for consistency with the base attendance view pattern.

**Files:**

- Create:
  `src/cube/model/views/attendance/student_attendance_streaks_detail.yml`

- [ ] **Step 1: Write the view file**

```yaml
views:
  - name: student_attendance_streaks_detail
    description: >-
      Row-level student attendance streak records. One row per student x
      consecutive run of the same attendance code. streak_start_date anchors the
      Cube time dimension — apply date filters here to slice by streak start.
      streak_end_date is a raw dimension (not joined to dates). attendance_code
      is the code repeated across all days of the streak.
      streak_length_membership counts school days; streak_length_calendar counts
      calendar days including weekends and holidays. Use for investigating
      absence run lengths or identifying students with long uninterrupted
      absence streaks.

    cubes:
      - join_path: student_attendance_streaks
        includes:
          - count_streaks
          - count_students_with_streaks
          - avg_streak_length_membership
          - avg_streak_length_calendar
          - max_streak_length_membership
          - streak_start_date
          - streak_end_date
          - academic_year
          - attendance_code
          - streak_length_membership
          - streak_length_calendar

      - join_path: student_attendance_streaks.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - academic_year

      - join_path: student_attendance_streaks.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_attendance_streaks.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_attendance_streaks.student_enrollments
        prefix: true
        includes:
          - student_enrollment_key
          - grade_level
          - graduation_year

      - join_path: student_attendance_streaks.student_enrollments.students
        prefix: true
        includes:
          - student_key
          - full_name
          - birth_date
          - lea_student_identifier
          - state_student_identifier
          - gender_identity
          - race
          - enrollment_status

    meta:
      folders:
        - name: Streak
          members:
            - streak_start_date
            - streak_end_date
            - academic_year
            - attendance_code
            - streak_length_membership
            - streak_length_calendar
        - name: Date
          members:
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_academic_year
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - locations_campus
            - locations_city
            - regions_region_name
            - regions_state
        - name: Student
          members:
            - students_student_key
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
            - students_gender_identity
            - students_race
            - students_enrollment_status
        - name: Enrollment
          members:
            - student_enrollments_student_enrollment_key
            - student_enrollments_grade_level
            - student_enrollments_graduation_year

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
      - group: cube-access-student-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/attendance/student_attendance_streaks_detail.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
folder_names = [f['name'] for f in view['meta']['folders']]
print('folders:', folder_names)
"
```

Expected output:

```text
view name: student_attendance_streaks_detail
join paths: ['student_attendance_streaks', 'student_attendance_streaks.dates', 'student_attendance_streaks.student_enrollments.locations', 'student_attendance_streaks.student_enrollments.locations.regions', 'student_attendance_streaks.student_enrollments', 'student_attendance_streaks.student_enrollments.students']
access groups: ['detail-access', 'cube-access-student-pii']
folders: ['Streak', 'Date', 'Location', 'Student', 'Enrollment']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/views/attendance/student_attendance_streaks_detail.yml
git commit -m "feat(cube): add student_attendance_streaks_detail view"
```

---

## Task 6: `student_attendance_streaks_summary` view

Summary view: aggregate-safe dimensions only. No `student_enrollment_key` or
`student_key`. Date dimension anchored on `streak_start_date` via the `dates`
join. Single `summary-access` policy.

**Files:**

- Create:
  `src/cube/model/views/attendance/student_attendance_streaks_summary.yml`

- [ ] **Step 1: Write the view file**

```yaml
views:
  - name: student_attendance_streaks_summary
    description: >-
      Aggregated student attendance streak analysis. Use for school/region
      roll-ups of streak counts, average streak length, and attendance code
      breakdowns. No individual student identifiers. Date filters anchor on
      streak_start_date (joined to dates cube). Filter by attendance_code to
      focus on a specific streak type (e.g., absences only).

    cubes:
      - join_path: student_attendance_streaks
        includes:
          - count_streaks
          - count_students_with_streaks
          - avg_streak_length_membership
          - avg_streak_length_calendar
          - max_streak_length_membership
          - academic_year
          - attendance_code

      - join_path: student_attendance_streaks.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - academic_year

      - join_path: student_attendance_streaks.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_attendance_streaks.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_attendance_streaks.student_enrollments
        prefix: true
        includes:
          - grade_level
          - graduation_year

      - join_path: student_attendance_streaks.student_enrollments.students
        prefix: true
        includes:
          - gender_identity
          - race

    meta:
      folders:
        - name: Streak
          members:
            - academic_year
            - attendance_code
        - name: Date
          members:
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_academic_year
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - locations_campus
            - locations_city
            - regions_region_name
            - regions_state
        - name: Student
          members:
            - students_gender_identity
            - students_race
        - name: Enrollment
          members:
            - student_enrollments_grade_level
            - student_enrollments_graduation_year

    access_policy:
      # No direct student identifiers — demographic dimensions are aggregate
      # breakdowns only.
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/attendance/student_attendance_streaks_summary.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_attendance_streaks_summary
join paths: ['student_attendance_streaks', 'student_attendance_streaks.dates', 'student_attendance_streaks.student_enrollments.locations', 'student_attendance_streaks.student_enrollments.locations.regions', 'student_attendance_streaks.student_enrollments', 'student_attendance_streaks.student_enrollments.students']
access groups: ['summary-access']
```

- [ ] **Step 3: Run the full cube test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/attendance/student_attendance_streaks_summary.yml
git commit -m "feat(cube): add student_attendance_streaks_summary view"
```

---

## Validation in Cube Cloud Dev Mode

After all tasks are committed and pushed, validate in Cube Cloud Dev Mode. Add
the branch by name in Cube Cloud → Data Model → Dev Mode. Dev Mode is the only
environment where server `console.log` is visible.

**Check 1 — Interventions model loads:**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["student_attendance_interventions_summary.count_interventions"],"limit":1}}' \
  | jq '.sql'
```

Expected: a SQL string containing `fct_student_attendance_interventions` in the
FROM clause, joined to `dim_student_attendance_intervention_types`.

**Check 2 — Streaks model loads:**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["student_attendance_streaks_summary.count_streaks"],"limit":1}}' \
  | jq '.sql'
```

Expected: a SQL string containing `fct_student_attendance_streaks` in the FROM
clause.

**Check 3 — New views appear in meta:**

The Cube MCP `meta` tool should list all four new view names:
`student_attendance_interventions_detail`,
`student_attendance_interventions_summary`, `student_attendance_streaks_detail`,
`student_attendance_streaks_summary`.

**Check 4 — `isStudentMember` gate fires correctly:**

Compile a query with a user who has `detail-access` but no
`cube-access-student-data`. The SQL for any of the four new views should contain
`WHERE (1 = 0)` — `queryRewrite` strips all `student_*`-prefixed members and
injects the default-deny filter.

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-for-user-without-cube-access-student-data>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["student_attendance_interventions_summary.count_interventions"],"limit":1}}' \
  | jq '.sql' | grep -c "1 = 0"
```

Expected: `1`.

**Check 5 — Intervention inlined dim join is correct:**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"dimensions":["student_attendance_interventions_detail.family_communication_reason","student_attendance_interventions_detail.absence_threshold"],"measures":["student_attendance_interventions_detail.count_interventions"],"limit":10}}' \
  | jq '.sql'
```

Expected: SQL contains
`LEFT JOIN kipptaf_marts.dim_student_attendance_intervention_types` in the
inlined `sql:` subquery, not as a Cube-managed join.
