> **Measures: not implemented in this pass.** Skip all `measures:` sections when
> writing cube files — dimensions, joins, and `public: false` only. Remove
> measure names from view `includes:` lists (keep dimension names only). Add
> measures on demand as analysts request specific aggregations.

# Cube Student Section Enrollments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `student_section_enrollments` cube and two consumer views
(`student_section_enrollments_detail`, `student_section_enrollments_summary`) to
the Cube semantic layer. This cube answers roster questions — who is enrolled in
what section, and who teaches it — without requiring a fact table.

**Prerequisite:** Plan 0 (`2026-06-01-cube-model-yaml-implementation.md`) must
be complete. The `student_enrollments` and `students` cubes must exist. The
staff-core plan must be complete before the `staff` join path in views is
functional — the cube file can be created now, but views that traverse
`student_section_enrollments.staff` will fail to load until `staff.yml` exists.

**Architecture:** One cube file in `src/cube/model/cubes/students/`. Two view
files in `src/cube/model/views/students/`. The cube inlines
`dim_course_sections`, `dim_courses`, and a filtered
`bridge_course_section_teachers` (excluding "Gradebook Access (edit)" rows) in
its `sql:` block.

**Grain:** One row per student × section enrollment × teacher assignment.
Sections with co-teachers produce multiple rows per student — one per
instructional teacher. "Gradebook Access (edit)" role assignments are excluded
from the SQL block entirely — they are administrative access grants, not
teaching relationships.

**Role values (from prod):**

| Role                    | Teaching? | Notes                                                |
| ----------------------- | --------- | ---------------------------------------------------- |
| Lead Teacher            | ✅        | Primary teacher; ~1 per section                      |
| Co-teacher              | ✅        | Simultaneous with Lead Teacher in co-taught sections |
| Blended Learning        | ✅        | Second instructional teacher                         |
| Job Share Teacher       | ✅        | Split-role teaching assignment                       |
| PhysEd Share            | ✅        | Split PE teaching                                    |
| Gradebook Access (edit) | ❌        | Admin access only — excluded from cube               |

**Fan-out behavior:** Because co-teachers and job-share arrangements produce
multiple simultaneous teacher assignments per section, a student in a co-taught
section will appear multiple times. Analysts must use one of:

- `is_lead_teacher = true` — one row per student per section (primary teacher
  only)
- Filter by `teacher_staff_key` — scoped to one teacher's students
- Filter by `teacher_role` — scoped to a specific role
- `count_distinct(student_enrollment_key)` — always correct for student counts

**Tech Stack:** Cube YAML (`src/cube/model/`), Python (`pytest`, `pyyaml`)

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

---

## Task 1: Schema validation test extension

The existing `test_cube_schema.py` covers all cubes via `rglob` — no changes
needed. Run it after Task 2 to confirm the new cube has no `dim_`/`fct_` prefix.

- [ ] **Step 1: Confirm existing test will cover new cube**

```bash
uv run pytest tests/cube/test_cube_schema.py -v 2>&1 | tail -5
```

Expected: all existing tests PASS (Plan 0 prerequisite).

---

## Task 2: `student_section_enrollments` cube

Inlines `dim_course_sections`, `dim_courses`, and the filtered teacher bridge
into the `sql:` block. Joins `student_enrollments` (for location/region/student
traversal), `terms` (for AY/semester context via `term_key` on
`dim_student_section_enrollments`), and `staff` (for teacher name and PII).

**Files:**

- Create: `src/cube/model/cubes/students/student_section_enrollments.yml`

- [ ] **Step 1: Write the cube file**

Write the following as the complete content of
`src/cube/model/cubes/students/student_section_enrollments.yml`:

```yaml
cubes:
  - name: student_section_enrollments
    public: false
    # Inlines dim_course_sections, dim_courses, and bridge_course_section_teachers
    # (teaching roles only — "Gradebook Access (edit)" excluded).
    # Grain: student_section_enrollment_key x teacher_assignment.
    # Sections with co-teachers produce multiple rows per student.
    sql: |
      SELECT
        sse.student_section_enrollment_key,
        sse.student_enrollment_key,
        sse.course_section_key,
        sse.term_key,
        sse.academic_year,
        sse.entry_date,
        sse.exit_date,
        sse.is_dropped_section,
        sse.is_dropped_course,
        cs.course_key,
        cs.identifier        AS section_identifier,
        cs.period            AS section_period,
        cs.room              AS section_room,
        c.course_code,
        c.course_title,
        c.credit_type,
        c.academic_subject,
        c.credits            AS course_credits,
        bct.staff_key        AS teacher_staff_key,
        bct.role             AS teacher_role,
        bct.role = 'Lead Teacher' AS is_lead_teacher,
        bct.effective_start_date AS teacher_effective_start_date,
        bct.effective_end_date   AS teacher_effective_end_date
      FROM kipptaf_marts.dim_student_section_enrollments sse
      JOIN kipptaf_marts.dim_course_sections cs
        ON cs.course_section_key = sse.course_section_key
      JOIN kipptaf_marts.dim_courses c
        ON c.course_key = cs.course_key
      -- Teaching roles only — "Gradebook Access (edit)" is an admin grant,
      -- not a teaching relationship.
      LEFT JOIN kipptaf_marts.bridge_course_section_teachers bct
        ON bct.course_section_key = sse.course_section_key
        AND bct.role != 'Gradebook Access (edit)'

    joins:
      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

      - name: terms
        sql: "{terms.term_key} = {CUBE}.term_key"
        relationship: many_to_one

      # Requires staff-core plan to be complete before this join resolves.
      - name: staff
        sql: "{staff.staff_key} = {CUBE}.teacher_staff_key"
        relationship: many_to_one

      # Point-in-time manager resolver — mirrors the staff_work_history pattern.
      # Overlaps teacher assignment effective dates against reporting relationship
      # dates to find the manager active when the teacher was assigned.
      - name: staff_reporting_relationships
        sql: >
          {staff_reporting_relationships.staff_key} = {CUBE}.teacher_staff_key
          AND CAST({CUBE}.teacher_effective_start_date AS TIMESTAMP)
            <= {staff_reporting_relationships.effective_end_date} AND
          CAST({CUBE}.teacher_effective_end_date AS TIMESTAMP)
            >= {staff_reporting_relationships.effective_start_date}
        relationship: many_to_one

      - name: staff_manager
        sql: >
          {staff_manager.staff_key} =
          {staff_reporting_relationships.manager_staff_key}
        relationship: many_to_one

    dimensions:
      - name: student_section_enrollment_key
        sql: student_section_enrollment_key
        type: string
        primary_key: true

      - name: academic_year
        description:
          KIPP academic year (July start) for this section enrollment.
        sql: academic_year
        type: number
        public: true

      - name: entry_date
        description: Date the student entered this section enrollment.
        sql: CAST(entry_date AS TIMESTAMP)
        type: time
        public: true

      - name: exit_date
        description: Date the student exited this section enrollment.
        sql: CAST(exit_date AS TIMESTAMP)
        type: time
        public: true

      - name: is_dropped_section
        description: TRUE if the student dropped this specific section.
        sql: is_dropped_section
        type: boolean
        public: true

      - name: is_dropped_course
        description: TRUE if the student dropped the entire course.
        sql: is_dropped_course
        type: boolean
        public: true

      - name: section_identifier
        description: Section identifier string (e.g. "1(A)").
        sql: section_identifier
        type: string
        public: true

      - name: section_period
        description:
          Period expression encoding days and periods when section meets.
        sql: section_period
        type: string
        public: true

      - name: section_room
        description: Room number for this section.
        sql: section_room
        type: string
        public: true

      - name: course_code
        description: Course code.
        sql: course_code
        type: string
        public: true

      - name: course_title
        description: Course title.
        sql: course_title
        type: string
        public: true

      - name: credit_type
        description: Credit type for this course.
        sql: credit_type
        type: string
        public: true

      - name: academic_subject
        description:
          Academic subject area (e.g. Mathematics, English Language Arts).
        sql: academic_subject
        type: string
        public: true

      - name: course_credits
        description: Credit hours awarded for this course.
        sql: course_credits
        type: number
        public: true

      - name: teacher_staff_key
        description:
          Staff surrogate key for the teacher assigned to this section.
        sql: teacher_staff_key
        type: string
        public: true

      - name: teacher_role
        description: >-
          PowerSchool role for this teacher assignment. Teaching roles: Lead
          Teacher, Co-teacher, Blended Learning, Job Share Teacher, PhysEd
          Share. Filter to is_lead_teacher = true for one row per student per
          section.
        sql: teacher_role
        type: string
        public: true

      - name: is_lead_teacher
        description: >-
          TRUE when teacher_role = 'Lead Teacher'. Use as a filter to get one
          row per student per section (the primary teacher). Without this
          filter, co-taught sections produce multiple rows per student.
        sql: is_lead_teacher
        type: boolean
        public: true

      - name: teacher_effective_start_date
        description: Start date of this teacher's assignment to the section.
        sql: CAST(teacher_effective_start_date AS TIMESTAMP)
        type: time
        public: true

      - name: teacher_effective_end_date
        description: End date of this teacher's assignment to the section.
        sql: CAST(teacher_effective_end_date AS TIMESTAMP)
        type: time
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/students/student_section_enrollments.yml').read_text()
)
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
print('joins:', [j['name'] for j in cube['joins']])
dims = [d['name'] for d in cube['dimensions'] if not d.get('primary_key')]
print('dimension count:', len(dims))
print('dimensions:', dims)
"
```

Expected output:

```text
cube name: student_section_enrollments
public: False
joins: ['student_enrollments', 'terms', 'staff', 'staff_reporting_relationships', 'staff_manager']
dimension count: 17
dimensions: ['academic_year', 'entry_date', 'exit_date', 'is_dropped_section', 'is_dropped_course', 'section_identifier', 'section_period', 'section_room', 'course_code', 'course_title', 'credit_type', 'academic_subject', 'course_credits', 'teacher_staff_key', 'teacher_role', 'is_lead_teacher', 'teacher_effective_start_date', 'teacher_effective_end_date']
```

- [ ] **Step 3: Run schema test**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all PASS including new `students/student_section_enrollments.yml`.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/students/student_section_enrollments.yml
git commit -m "feat(cube): add student_section_enrollments cube — roster with section, course, and teacher context"
```

---

## Task 3: `student_section_enrollments_detail` view

Exposes the full roster with student PII (gated) and teacher staff dimensions
(requires staff-core). Filter guidance is critical in the description —
`is_lead_teacher = true` is the default anchor for avoiding fan-out.

**Files:**

- Create: `src/cube/model/views/students/student_section_enrollments_detail.yml`

- [ ] **Step 1: Create the directory if needed**

```bash
mkdir -p src/cube/model/views/students
```

- [ ] **Step 2: Write the view file**

Write the following as the complete content of
`src/cube/model/views/students/student_section_enrollments_detail.yml`:

```yaml
views:
  - name: student_section_enrollments_detail
    description: >-
      Row-level student section enrollment roster with course and teacher
      context. Grain: one row per student x section enrollment x teacher
      assignment (teaching roles only — Gradebook Access excluded).

      Fan-out warning: sections with co-teachers or job-share arrangements
      produce multiple rows per student — one per instructional teacher. Use one
      of the following anchors to avoid duplicates in row-level queries: (1)
      filter is_lead_teacher = true for the primary teacher only; (2) filter by
      teacher_staff_key to scope to one teacher's students; (3) filter by
      teacher_role for a specific role. For aggregate student counts,
      count_distinct(student_enrollment_key) is always correct.

      Teacher dimensions (staff join path) require the staff-core plan to be
      complete. Contains direct student identifiers — see access_policy for PII
      gating.

    cubes:
      - join_path: student_section_enrollments
        includes:
          - academic_year
          - entry_date
          - exit_date
          - is_dropped_section
          - is_dropped_course
          - section_identifier
          - section_period
          - section_room
          - course_code
          - course_title
          - credit_type
          - academic_subject
          - course_credits
          - teacher_staff_key
          - teacher_role
          - is_lead_teacher
          - teacher_effective_start_date
          - teacher_effective_end_date

      - join_path: student_section_enrollments.terms
        prefix: true
        includes:
          - academic_year
          - semester
          - term_name
          - term_code
          - term_type

      - join_path: student_section_enrollments.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: >-
          student_section_enrollments.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_section_enrollments.student_enrollments
        prefix: true
        includes:
          - student_enrollment_key
          - grade_level
          - graduation_year
          - entry_date
          - exit_date

      - join_path: student_section_enrollments.student_enrollments.students
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
          - is_gifted

      # Requires staff-core plan. Teacher name and PII fields.
      - join_path: student_section_enrollments.staff
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - work_email

    meta:
      folders:
        - name: Section
          members:
            - academic_year
            - entry_date
            - exit_date
            - is_dropped_section
            - is_dropped_course
            - section_identifier
            - section_period
            - section_room
        - name: Course
          members:
            - course_code
            - course_title
            - credit_type
            - academic_subject
            - course_credits
        - name: Teacher
          members:
            - teacher_staff_key
            - teacher_role
            - is_lead_teacher
            - teacher_effective_start_date
            - teacher_effective_end_date
        - name: Term
          members:
            - terms_academic_year
            - terms_semester
            - terms_term_name
            - terms_term_code
            - terms_term_type
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
            - students_is_gifted
        - name: Enrollment
          members:
            - student_enrollments_student_enrollment_key
            - student_enrollments_grade_level
            - student_enrollments_graduation_year
            - student_enrollments_entry_date
            - student_enrollments_exit_date
        - name: Staff
          members:
            - staff_staff_key
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
      - group: cube-access-student-pii
        member_level:
          includes: "*"
          excludes:
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
      - group: cube-access-staff-pii
        member_level:
          includes: "*"
          excludes:
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
```

- [ ] **Step 3: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/views/students/student_section_enrollments_detail.yml').read_text()
)
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_section_enrollments_detail
join paths: ['student_section_enrollments', 'student_section_enrollments.terms', 'student_section_enrollments.student_enrollments.locations', 'student_section_enrollments.student_enrollments.locations.regions', 'student_section_enrollments.student_enrollments', 'student_section_enrollments.student_enrollments.students', 'student_section_enrollments.staff']
access groups: ['detail-access', 'cube-access-student-pii', 'cube-access-staff-pii']
```

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/students/student_section_enrollments_detail.yml
git commit -m "feat(cube): add student_section_enrollments_detail view"
```

---

## Task 4: `student_section_enrollments_summary` view

Aggregate-safe view: no individual student identifiers, no teacher PII. Exposes
section, course, and demographic dimensions for roll-up analysis.

**Files:**

- Create:
  `src/cube/model/views/students/student_section_enrollments_summary.yml`

- [ ] **Step 1: Write the view file**

Write the following as the complete content of
`src/cube/model/views/students/student_section_enrollments_summary.yml`:

```yaml
views:
  - name: student_section_enrollments_summary
    description: >-
      Aggregated student section enrollment roster. No direct student or staff
      identifiers. Use for section-level breakdowns: enrollment counts by
      course, subject area, grade level, or school.

      Fan-out warning: sections with co-teachers produce multiple rows per
      student. Filter is_lead_teacher = true for deduplicated student counts, or
      use count_distinct(student_enrollment_key) for aggregates.

    cubes:
      - join_path: student_section_enrollments
        includes:
          - academic_year
          - is_dropped_section
          - is_dropped_course
          - section_identifier
          - section_period
          - course_code
          - course_title
          - credit_type
          - academic_subject
          - course_credits
          - teacher_role
          - is_lead_teacher

      - join_path: student_section_enrollments.terms
        prefix: true
        includes:
          - academic_year
          - semester
          - term_name
          - term_code
          - term_type

      - join_path: student_section_enrollments.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: >-
          student_section_enrollments.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_section_enrollments.student_enrollments
        prefix: true
        includes:
          - grade_level
          - graduation_year

      - join_path: student_section_enrollments.student_enrollments.students
        prefix: true
        includes:
          - gender_identity
          - race
          - is_gifted

    meta:
      folders:
        - name: Section
          members:
            - academic_year
            - is_dropped_section
            - is_dropped_course
            - section_identifier
            - section_period
        - name: Course
          members:
            - course_code
            - course_title
            - credit_type
            - academic_subject
            - course_credits
        - name: Teacher
          members:
            - teacher_role
            - is_lead_teacher
        - name: Term
          members:
            - terms_academic_year
            - terms_semester
            - terms_term_name
            - terms_term_code
            - terms_term_type
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
        - name: Enrollment
          members:
            - student_enrollments_grade_level
            - student_enrollments_graduation_year

    access_policy:
      # No direct student or staff identifiers.
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
    Path('src/cube/model/views/students/student_section_enrollments_summary.yml').read_text()
)
view = data['views'][0]
print('view name:', view['name'])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_section_enrollments_summary
access groups: ['summary-access']
```

- [ ] **Step 3: Run full cube test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/students/student_section_enrollments_summary.yml
git commit -m "feat(cube): add student_section_enrollments_summary view"
```

---

## Task 5: Embed teacher and manager dimensions into attendance views

Add teacher, teacher manager, and course/section context to
`student_attendance_detail` and `student_attendance_summary` by joining through
the new `student_section_enrollments` cube. Also adds the required join from
`student_attendance` cube to `student_section_enrollments`.

**Prerequisites:** Task 2 (`student_section_enrollments` cube) must be complete.
The `staff_reporting_relationships` and `staff_manager` cubes must exist (they
are already in `src/cube/model/cubes/staff/`).

**Fan-out note:** Joining attendance → student section enrollments produces
multiple rows per attendance day for students in co-taught sections (one per
teacher). This is expected — queries that group by teacher naturally scope to
one teacher's students. Queries that do not use teacher dimensions do not
traverse this join, so there is no fan-out cost for existing attendance queries.

**Files:**

- Modify: `src/cube/model/cubes/attendance/student_attendance.yml`
- Modify: `src/cube/model/views/attendance/student_attendance_detail.yml`
- Modify: `src/cube/model/views/attendance/student_attendance_summary.yml`

- [ ] **Step 1: Add `student_section_enrollments` join to `student_attendance`
      cube**

In `src/cube/model/cubes/attendance/student_attendance.yml`, add the following
join after the existing `terms` join:

```yaml
# Joins to section enrollment roster for teacher and manager dimensions.
# one_to_many: one attendance row fans to N rows when a student has N
# teachers (co-taught sections). Fan-out only materialises when a teacher
# dimension is included in the query.
- name: student_section_enrollments
  sql: >
    {student_section_enrollments.student_enrollment_key} =
    {student_enrollments.student_enrollment_key}
  relationship: one_to_many
```

- [ ] **Step 2: Verify the cube YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/attendance/student_attendance.yml').read_text()
)
cube = data['cubes'][0]
joins = [j['name'] for j in cube['joins']]
print('joins:', joins)
assert 'student_section_enrollments' in joins
print('OK')
"
```

- [ ] **Step 3: Add teacher/manager join paths to `student_attendance_detail`**

In `src/cube/model/views/attendance/student_attendance_detail.yml`, append the
following join paths after the existing `student_attendance.school_calendars`
block:

```yaml
# Teacher dimensions — requires student_section_enrollments cube (Task 2)
# and staff-core plan. Fan-out: one attendance row per teacher in
# co-taught sections. Filter is_lead_teacher = true for one row per day.
- join_path: student_attendance.student_section_enrollments
  prefix: true
  includes:
    - course_code
    - course_title
    - academic_subject
    - section_identifier
    - section_period
    - teacher_role
    - is_lead_teacher
    - is_dropped_section

- join_path: student_attendance.student_section_enrollments.staff
  prefix: true
  includes:
    - staff_key
    - full_name
    - first_name
    - last_name
    - work_email

- join_path: >-
    student_attendance.student_section_enrollments.staff_reporting_relationships.staff_manager
  prefix: true
  includes:
    - staff_key
    - full_name
    - first_name
    - last_name
    - work_email
```

Also add a `Teacher` folder and a `Manager` folder to the `meta.folders` block:

```yaml
- name: Teacher
  members:
    - student_section_enrollments_course_code
    - student_section_enrollments_course_title
    - student_section_enrollments_academic_subject
    - student_section_enrollments_section_identifier
    - student_section_enrollments_section_period
    - student_section_enrollments_teacher_role
    - student_section_enrollments_is_lead_teacher
    - student_section_enrollments_is_dropped_section
    - student_section_enrollments_staff_staff_key
    - student_section_enrollments_staff_full_name
    - student_section_enrollments_staff_first_name
    - student_section_enrollments_staff_last_name
- name: Manager
  members:
    - student_section_enrollments_staff_manager_staff_key
    - student_section_enrollments_staff_manager_full_name
    - student_section_enrollments_staff_manager_first_name
    - student_section_enrollments_staff_manager_last_name
```

And update the `access_policy` to add teacher/manager PII to the correct gates.
The detail view uses additive includes — extend the two existing blocks:

- In the `detail-access` block, add to `excludes:`:
  - `student_section_enrollments_staff_full_name`
  - `student_section_enrollments_staff_first_name`
  - `student_section_enrollments_staff_last_name`
  - `student_section_enrollments_staff_work_email`
  - `student_section_enrollments_staff_manager_full_name`
  - `student_section_enrollments_staff_manager_first_name`
  - `student_section_enrollments_staff_manager_last_name`
  - `student_section_enrollments_staff_manager_work_email`

- In the `cube-access-student-pii` block, add to `includes:` (or keep
  `includes: "*"` which already covers all fields that aren't in the
  `detail-access` excludes list — verify the current shape before editing).

- Add a new `cube-access-staff-pii` block:

```yaml
- group: cube-access-staff-pii
  member_level:
    includes:
      - student_section_enrollments_staff_full_name
      - student_section_enrollments_staff_first_name
      - student_section_enrollments_staff_last_name
      - student_section_enrollments_staff_work_email
      - student_section_enrollments_staff_manager_full_name
      - student_section_enrollments_staff_manager_first_name
      - student_section_enrollments_staff_manager_last_name
      - student_section_enrollments_staff_manager_work_email
```

- [ ] **Step 4: Add teacher/manager join paths to `student_attendance_summary`**

In `src/cube/model/views/attendance/student_attendance_summary.yml`, append the
following join paths after the existing `student_attendance.terms` block:

```yaml
# Teacher dimensions — no PII (names excluded). staff_key is a surrogate,
# not a direct identifier. Allows grouping by teacher or manager without
# exposing personal information.
- join_path: student_attendance.student_section_enrollments
  prefix: true
  includes:
    - course_title
    - academic_subject
    - teacher_role
    - is_lead_teacher

- join_path: student_attendance.student_section_enrollments.staff
  prefix: true
  includes:
    - staff_key

- join_path: >-
    student_attendance.student_section_enrollments.staff_reporting_relationships.staff_manager
  prefix: true
  includes:
    - staff_key
```

Also add a `Teacher` folder and a `Manager` folder to the `meta.folders` block:

```yaml
- name: Teacher
  members:
    - student_section_enrollments_course_title
    - student_section_enrollments_academic_subject
    - student_section_enrollments_teacher_role
    - student_section_enrollments_is_lead_teacher
    - student_section_enrollments_staff_staff_key
- name: Manager
  members:
    - student_section_enrollments_staff_manager_staff_key
```

The summary view has a single `summary-access` block with `includes: "*"` — no
changes needed to `access_policy` since no PII fields are added.

- [ ] **Step 5: Verify both view YAMLs parse**

```bash
uv run python -c "
import yaml
from pathlib import Path
for name in ['student_attendance_detail', 'student_attendance_summary']:
    data = yaml.safe_load(
        Path(f'src/cube/model/views/attendance/{name}.yml').read_text()
    )
    view = data['views'][0]
    paths = [c['join_path'] for c in view['cubes']]
    teacher_paths = [p for p in paths if 'section_enrollment' in str(p)]
    print(f'{name}: teacher join paths = {teacher_paths}')
    assert len(teacher_paths) >= 3, f'expected 3 teacher join paths in {name}'
print('OK')
"
```

- [ ] **Step 6: Run full cube test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/cube/model/cubes/attendance/student_attendance.yml
git add src/cube/model/views/attendance/student_attendance_detail.yml
git add src/cube/model/views/attendance/student_attendance_summary.yml
git commit -m "feat(cube): add teacher and manager dimensions to attendance views via student_section_enrollments"
```

---

## Execution order note

This plan can run immediately after Plan 0. The `staff` join in the cube and
detail view will fail to resolve at query time until the staff-core plan runs —
no schema load error, but traversing the `staff` join path returns an error.
Implement staff-core before relying on teacher name/email dimensions.

Add this plan to Plan 0's execution order tree:

```text
0. cube-model-yaml-implementation       (done)
   ├── cube-attendance-extension-implementation  (done)
   ├── cube-student-section-enrollments-implementation  ← add here
   ├── cube-assessments-implementation
   ...
```

---

## Validation in Cube Cloud

After all tasks are committed and pushed, validate in Cube Cloud Dev Mode.

**Check 1 — Model loads:**

Query `student_section_enrollments_summary` with `academic_year` and
`course_title` dimensions. The compiled SQL should show
`dim_student_section_enrollments` as the FROM source with JOINs to
`dim_course_sections`, `dim_courses`, and the filtered
`bridge_course_section_teachers`.

**Check 2 — Gradebook Access excluded:**

The compiled SQL should have `bct.role != 'Gradebook Access (edit)'` in the
bridge JOIN condition.

**Check 3 — `is_lead_teacher` computed correctly:**

Query with `is_lead_teacher` as a dimension. Filter to `is_lead_teacher = true`
and verify the result set has at most one row per
`student_section_enrollment_key`.

**Check 4 — Fan-out visible without filter:**

Query `student_section_enrollments_summary` without any teacher filter, grouping
by `section_identifier` and `locations_abbreviation`. Sections with co-teachers
should show multiple rows (one per teacher assignment) when `count(*)` is used,
but `count_distinct(student_enrollment_key)` should return the correct student
count.
