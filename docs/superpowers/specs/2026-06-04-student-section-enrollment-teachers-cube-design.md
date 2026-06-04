# Student Section Enrollment Teachers — Cube Design

**Date:** 2026-06-04 **Status:** Active  
**Branch:** `cristinabaldor/feat/claude-cube-model-yaml-design`

## Overview

Add teacher and manager dimensions to the Cube semantic layer so that attendance
and assessment views can answer questions like:

- Which teacher's students are chronically absent?
- How are this teacher's students performing on an assessment?
- How do results look grouped by coaching group, grade level chair, or AP?

No new dbt mart models are needed. All required tables already exist in
`kipptaf_marts`. This spec covers one new Cube cube and the view changes to
`student_attendance_detail` and `student_attendance_summary` that expose teacher
and manager dimensions.

## Goals

- One new Cube cube (`student_section_enrollment_teachers`) that inlines
  `dim_student_section_enrollments`, `dim_course_sections`, `dim_courses`, and
  `bridge_course_section_teachers` into a single SQL surface.
- Point-in-time teacher resolution: teacher assignment effective dates overlap
  the student's section enrollment dates.
- Point-in-time manager resolution via the existing
  `staff_reporting_relationships` cube and `staff_manager` cube — identical join
  pattern to `staff_work_history`.
- Teacher and manager dimensions added to `student_attendance_detail` and
  `student_attendance_summary` views as `join_path` includes.
- Fan-out is safe in fact views: attendance and assessment queries always carry
  a date filter, which pins teacher and manager to a single effective row.

## Non-Goals

- No new dbt mart models.
- No standalone `student_section_enrollments_detail` view — teacher/manager dims
  are embedded into fact views, not exposed as a standalone surface.
- Manager traversal beyond one level (direct manager only for now).
- Assessment view changes — covered when an assessment Cube view is built.

## Data Model

### Existing mart tables used (no changes)

| Table                             | Grain                                 | Key fields                                                                                                  |
| --------------------------------- | ------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `dim_student_section_enrollments` | CC record (student × section stint)   | `student_section_enrollment_key`, `student_enrollment_key`, `course_section_key`, `entry_date`, `exit_date` |
| `dim_course_sections`             | Section instance per region           | `course_section_key`, `course_key`                                                                          |
| `dim_courses`                     | Course per region                     | `course_key`, `course_code`, `course_title`, `academic_subject`                                             |
| `bridge_course_section_teachers`  | Section × teacher × assignment period | `course_section_key`, `staff_key`, `role`, `effective_start_date`, `effective_end_date`                     |

### Existing Cube cubes reused (no changes)

| Cube                            | Used for                                       |
| ------------------------------- | ---------------------------------------------- |
| `staff`                         | Teacher name and identifiers                   |
| `staff_manager`                 | Manager name and identifiers (extends `staff`) |
| `staff_reporting_relationships` | Point-in-time teacher → manager resolution     |

## New Cube: `student_section_enrollment_teachers`

File: `src/cube/model/cubes/students/student_section_enrollment_teachers.yml`

### SQL

Inlines four mart tables. The teacher join uses a date-overlap predicate
(half-open interval) matching
`bridge_course_section_teachers.effective_start_date` / `effective_end_date`
against the student's section `entry_date` / `exit_date`. This is a LEFT JOIN so
students in sections with no teacher assignment still appear.

```sql
SELECT
  sse.student_section_enrollment_key,
  sse.student_enrollment_key,
  sse.academic_year,
  sse.entry_date,
  sse.exit_date,
  sse.is_dropped_section,
  sse.is_dropped_course,
  cs.identifier         AS section_identifier,
  cs.period,
  cs.room,
  cr.course_code,
  cr.course_title,
  cr.credit_type,
  cr.academic_subject,
  bct.staff_key         AS teacher_staff_key,
  bct.role              AS teacher_role,
  bct.effective_start_date AS teacher_effective_start_date,
  bct.effective_end_date   AS teacher_effective_end_date,
FROM kipptaf_marts.dim_student_section_enrollments sse
JOIN kipptaf_marts.dim_course_sections cs
  ON cs.course_section_key = sse.course_section_key
JOIN kipptaf_marts.dim_courses cr
  ON cr.course_key = cs.course_key
LEFT JOIN kipptaf_marts.bridge_course_section_teachers bct
  ON bct.course_section_key = sse.course_section_key
  AND sse.entry_date < bct.effective_end_date
  AND sse.exit_date  > bct.effective_start_date
```

### Joins

The three outward joins mirror the `staff_work_history` pattern exactly:

```yaml
joins:
  - name: staff
    sql: "{staff.staff_key} = {CUBE}.teacher_staff_key"
    relationship: many_to_one

  - name: staff_reporting_relationships
    sql: >
      {staff_reporting_relationships.staff_key} = {CUBE}.teacher_staff_key AND
      CAST({CUBE}.teacher_effective_start_date AS TIMESTAMP)
        <= {staff_reporting_relationships.effective_end_date} AND
      CAST({CUBE}.teacher_effective_end_date AS TIMESTAMP)
        >= {staff_reporting_relationships.effective_start_date}
    relationship: many_to_one

  - name: staff_manager
    sql: >
      {staff_manager.staff_key} =
      {staff_reporting_relationships.manager_staff_key}
    relationship: many_to_one
```

### Dimensions

| Name                             | Type    | Notes                                                            |
| -------------------------------- | ------- | ---------------------------------------------------------------- |
| `student_section_enrollment_key` | string  | PK                                                               |
| `student_enrollment_key`         | string  | FK to `student_enrollments` cube — join anchor for fact views    |
| `academic_year`                  | number  |                                                                  |
| `entry_date`                     | time    | Cast to TIMESTAMP                                                |
| `exit_date`                      | time    | Cast to TIMESTAMP                                                |
| `is_dropped_section`             | boolean |                                                                  |
| `is_dropped_course`              | boolean |                                                                  |
| `section_identifier`             | string  | Section number                                                   |
| `period`                         | string  |                                                                  |
| `room`                           | string  |                                                                  |
| `course_code`                    | string  |                                                                  |
| `course_title`                   | string  |                                                                  |
| `credit_type`                    | string  |                                                                  |
| `academic_subject`               | string  | Subject-area crosswalk — useful for filtering by ELA, Math, etc. |
| `teacher_staff_key`              | string  | FK to `staff` cube                                               |
| `teacher_role`                   | string  | e.g. "Lead Teacher", "Co-Teacher" — consumers can filter         |
| `teacher_effective_start_date`   | time    | Cast to TIMESTAMP — used in manager join                         |
| `teacher_effective_end_date`     | time    | Cast to TIMESTAMP — used in manager join                         |

## Join from `student_attendance` to the new cube

The `student_attendance` cube joins to `student_enrollments` via
`student_enrollment_key` (already exists). The new cube joins into that same
path via `student_enrollment_key`:

```yaml
# Added to student_attendance joins:
- name: student_section_enrollment_teachers
  sql: >
    {student_section_enrollment_teachers.student_enrollment_key} =
    {student_enrollments.student_enrollment_key}
  relationship: one_to_many
```

Fan-out note: one attendance row fans to N rows when a student has N teachers
(e.g. a co-taught class). This is expected and correct — consumers filter
`teacher_role` or group by teacher. The fan-out only materializes when a teacher
dimension is included in the query; without it, the join is not traversed.

## View changes

### `student_attendance_detail`

Add four new `join_path` blocks after the existing
`student_enrollments.students` block:

```yaml
- join_path: student_attendance.student_section_enrollment_teachers
  prefix: true
  includes:
    - section_identifier
    - period
    - course_code
    - course_title
    - academic_subject
    - teacher_role
    - is_dropped_section

- join_path: student_attendance.student_section_enrollment_teachers.staff
  prefix: true
  includes:
    - staff_key
    - full_name
    - first_name
    - last_name

- join_path: >-
    student_attendance.student_section_enrollment_teachers.staff_reporting_relationships.staff_manager
  prefix: true
  includes:
    - staff_key
    - full_name
    - first_name
    - last_name
```

PII gating: teacher and manager `full_name`, `first_name`, `last_name` go into
the `cube-access-staff-pii` block; `staff_key` fields go into `detail-access`.

### `student_attendance_summary`

Add the same teacher and manager join paths but expose only non-PII grouping
dimensions:

```yaml
- join_path: student_attendance.student_section_enrollment_teachers
  prefix: true
  includes:
    - course_title
    - academic_subject
    - teacher_role

- join_path: student_attendance.student_section_enrollment_teachers.staff
  prefix: true
  includes:
    - staff_key

- join_path: >-
    student_attendance.student_section_enrollment_teachers.staff_reporting_relationships.staff_manager
  prefix: true
  includes:
    - staff_key
```

Summary views carry no PII by convention. Teacher and manager names are PII
(`cube-access-staff-pii`) and are excluded from the summary surface. `staff_key`
is a surrogate and is not PII.

## Access policy changes

### `student_attendance_detail`

The detail view uses the additive includes pattern (established in
`staff_detail`). Extend the two existing blocks:

- `detail-access` block: add `staff_key` fields for teacher and manager, plus
  non-PII section dims (`section_identifier`, `period`, `course_code`,
  `course_title`, `academic_subject`, `teacher_role`, `is_dropped_section`).
- `cube-access-staff-pii` block: add `full_name`, `first_name`, `last_name` for
  both teacher and manager (prefixed).

### `student_attendance_summary`

Single `summary-access` block with `includes: "*"` — no PII tier needed since
teacher/manager names are excluded at the view level.

## Folder metadata

Add a `Teacher` folder and a `Manager` folder to both views' `meta.folders`
blocks, following the existing folder pattern.

## Query examples

**Chronic absence by teacher (year-end):**

```text
measures: [student_attendance.count_chronically_absent_year_end]
dimensions: [
  student_section_enrollment_teachers_staff_full_name,
  student_section_enrollment_teachers_staff_staff_key,
]
filters: [{ member: student_attendance.is_latest_record, operator: equals, values: ["true"] }]
```

**CA grouped by manager (coaching group):**

```text
measures: [student_attendance.pct_chronically_absent_year_end]
dimensions: [
  student_section_enrollment_teachers_staff_manager_full_name,
  student_section_enrollment_teachers_academic_subject,
]
filters: [{ member: student_attendance.is_latest_record, operator: equals, values: ["true"] }]
```

## Files to create / modify

| Action | File                                                                    |
| ------ | ----------------------------------------------------------------------- |
| Create | `src/cube/model/cubes/students/student_section_enrollment_teachers.yml` |
| Modify | `src/cube/model/cubes/attendance/student_attendance.yml` — add join     |
| Modify | `src/cube/model/views/attendance/student_attendance_detail.yml`         |
| Modify | `src/cube/model/views/attendance/student_attendance_summary.yml`        |
