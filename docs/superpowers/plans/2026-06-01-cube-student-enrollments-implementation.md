> **Measures: not implemented in this pass** — with one exception.
> `count_students` already exists on the `student_enrollments` cube from the
> original YAML and is the primary measure for this domain. Keep it. Skip any
> additional measures.

# Cube Student Enrollments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing `student_enrollments` cube through two consumer
views (`student_enrollments_detail`, `student_enrollments_summary`) to enable
headcount and demographic questions without routing through a fact table.

**Prerequisite:** Plan 0 complete. `student_enrollments`, `students`, and
`locations` cubes exist at their post-rename names.

**Architecture:** The `student_enrollments` cube already exists in
`src/cube/model/cubes/students/student_enrollments.yml`. This plan makes one
small fix to the cube (expose `academic_year` publicly), then creates two views
in a new `views/students/` directory.

**Grain:** One row per student enrollment stint. A student who transfers between
schools mid-year has two rows (one per stint). A student enrolled across
multiple academic years has one row per year. Always filter to a specific
`academic_year` to avoid double-counting across years, or use
`count_distinct(student_key)` for unique-student counts across multiple years.

**Double-counting note:** `count_students` counts distinct
`student_enrollment_key` values — this is enrollment count, not student count.
Two students at the same school in the same year → 2. One student enrolled at
two schools in the same year → 2. One student across two years → 2. Filter to
`academic_year` + a single location for clean per-school-per-year counts.

**Tech Stack:** Cube YAML (`src/cube/model/`), Python (`pytest`, `pyyaml`)

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

---

## Task 1: Fix `student_enrollments` cube — expose `academic_year` publicly

`academic_year` is currently defined on the cube but not `public: true`, so it's
invisible to views. One-line change.

**Files:**

- Modify: `src/cube/model/cubes/students/student_enrollments.yml`

- [ ] **Step 1: Add `public: true` to the `academic_year` dimension**

In `student_enrollments.yml`, find the `academic_year` dimension and add
`public: true`:

```yaml
- name: academic_year
  description: >-
    KIPP academic year (July start) in which this enrollment falls. The calendar
    year in which the academic year begins (e.g., 2025 for the 2025-26 school
    year).
  sql: academic_year
  type: number
  public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/students/student_enrollments.yml').read_text()
)
cube = data['cubes'][0]
public_dims = [d['name'] for d in cube['dimensions'] if d.get('public')]
print('public dimensions:', public_dims)
"
```

Expected: `academic_year` appears in the public dimensions list.

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/cubes/students/student_enrollments.yml
git commit -m "fix(cube): expose academic_year publicly on student_enrollments cube"
```

---

## Task 2: Create `views/students/` directory and `student_enrollments_detail`

view

Detail view: exposes enrollment attributes and student PII (gated). Use for
drill-down to individual enrollment records or identifying specific students.

**Files:**

- Create: `src/cube/model/views/students/student_enrollments_detail.yml`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p src/cube/model/views/students
```

- [ ] **Step 2: Write the view file**

Write the following as the complete content of
`src/cube/model/views/students/student_enrollments_detail.yml`:

```yaml
views:
  - name: student_enrollments_detail
    description: >-
      Row-level student enrollment records. One row per enrollment stint — a
      student who transfers mid-year has two rows; a student enrolled across
      multiple years has one row per year.

      Double-counting warning: count_students counts distinct enrollment
      records, not distinct students. Always filter to a specific academic_year
      for per-year headcount. For unique student counts across multiple years,
      use count_distinct(student_key) from the students join path.

      Contains direct student identifiers — see access_policy for PII gating.

    cubes:
      - join_path: student_enrollments
        includes:
          - count_students
          - student_enrollment_key
          - academic_year
          - grade_level
          - graduation_year
          - entry_date
          - exit_date
          - is_retained_year

      - join_path: student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_enrollments.students
        prefix: true
        includes:
          - student_key
          - full_name
          - birth_date
          - lea_student_identifier
          - state_student_identifier
          - gender_identity
          - race
          - is_gifted
          - enrollment_status

    meta:
      folders:
        - name: Enrollment
          members:
            - student_enrollment_key
            - academic_year
            - grade_level
            - graduation_year
            - entry_date
            - exit_date
            - is_retained_year
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
            - students_is_gifted
            - students_enrollment_status

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

- [ ] **Step 3: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/views/students/student_enrollments_detail.yml').read_text()
)
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_enrollments_detail
join paths: ['student_enrollments', 'student_enrollments.locations', 'student_enrollments.locations.regions', 'student_enrollments.students']
access groups: ['detail-access', 'cube-access-student-pii']
```

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/students/student_enrollments_detail.yml
git commit -m "feat(cube): add student_enrollments_detail view"
```

---

## Task 3: `student_enrollments_summary` view

Summary view: aggregate-safe demographics and location breakdowns, no individual
identifiers.

**Files:**

- Create: `src/cube/model/views/students/student_enrollments_summary.yml`

- [ ] **Step 1: Write the view file**

Write the following as the complete content of
`src/cube/model/views/students/student_enrollments_summary.yml`:

```yaml
views:
  - name: student_enrollments_summary
    description: >-
      Aggregated student enrollment for headcount and demographic breakdowns. No
      direct student identifiers — demographic dimensions (race,
      gender_identity, is_gifted) are aggregate breakdowns only.

      Double-counting warning: count_students counts distinct enrollment records
      per filter slice. Filter to a single academic_year for per-year headcount.
      Omitting academic_year sums across all years in scope, producing
      enrollment-years not student count.

    cubes:
      - join_path: student_enrollments
        includes:
          - count_students
          - academic_year
          - grade_level
          - graduation_year
          - is_retained_year

      - join_path: student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_enrollments.students
        prefix: true
        includes:
          - gender_identity
          - race
          - is_gifted
          - enrollment_status

    meta:
      folders:
        - name: Enrollment
          members:
            - academic_year
            - grade_level
            - graduation_year
            - is_retained_year
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
            - students_is_gifted
            - students_enrollment_status

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
data = yaml.safe_load(
    Path('src/cube/model/views/students/student_enrollments_summary.yml').read_text()
)
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_enrollments_summary
join paths: ['student_enrollments', 'student_enrollments.locations', 'student_enrollments.locations.regions', 'student_enrollments.students']
access groups: ['summary-access']
```

- [ ] **Step 3: Run the full cube test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/students/student_enrollments_summary.yml
git commit -m "feat(cube): add student_enrollments_summary view"
```

---

## Validation in Cube Cloud

After all tasks are committed and pushed, validate in Cube Cloud Dev Mode.

**Check 1 — Model loads and `academic_year` is queryable:**

Query `student_enrollments_summary` with `academic_year` and
`locations_abbreviation`. Should return enrollment counts per school per year
with no errors.

**Check 2 — Double-counting is visible:**

Query `student_enrollments_summary.count_students` with NO filters. The result
should be the total enrollment-year records across all years — a large number.
Then add `academic_year = 2025` and verify it drops to current-year enrollment
only.

**Check 3 — Views appear in meta:**

`student_enrollments_detail` and `student_enrollments_summary` appear. The
`student_enrollments` cube itself does not (it's `public: false`).
