# Cube Gradebook Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the gradebook domain in the Cube semantic layer — four fact
cubes covering term grades, category grades, assignment scores, and GPA
snapshots, with two views (detail and summary) exposing teacher context,
manager-at-date resolution, and student demographic breakdowns.

**Architecture:** All files land in `src/cube/model/`. Four fact cubes, all
`public: false`. `dim_student_section_enrollments`, `dim_course_sections`,
`dim_courses`, and `bridge_course_section_teachers` are INLINED into each
section-grain cube's `sql:` block — they have no independent analytical grain.
`fct_grades_gpa` is the exception: it joins `student_enrollments` directly (no
section key), so no course/section inline is needed. Two views:
`student_grades_detail` (group: `detail-access` + `cube-access-student-pii`) and
`student_grades_summary` (group: `summary-access`). Manager-at-date is resolved
via `staff_reporting_relationships` + `staff_manager` alias — both cubes are
assumed to exist from the staff core plan.

**Cube names:**

| dbt table                | Cube name                    |
| ------------------------ | ---------------------------- |
| `fct_grades_term`        | `student_grades_term`        |
| `fct_grades_category`    | `student_grades_category`    |
| `fct_grades_assignments` | `student_grades_assignments` |
| `fct_grades_gpa`         | `student_grades_gpa`         |

**Tech Stack:** Cube YAML (`src/cube/model/`), Python tests (`pytest`, `pyyaml`)

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

**Prerequisites:**

- Plan 0 (`2026-06-01-cube-model-yaml-implementation.md`) must be complete —
  cube names must not carry `dim_`/`fct_` prefixes and `withSyntheticGroups`
  must be wired in `cube.js`.
- Staff core plan must be complete — `staff`, `staff_reporting_relationships`,
  and `staff_manager` cubes must exist before this plan's join declarations
  reference them.

---

## View strategy

`fct_grades_term` and `fct_grades_category` share the same analytical grain
(student × section × term) and expose compatible dimensions.
`fct_grades_assignments` is finer (student × assignment). `fct_grades_gpa` is
coarser (student × term, no section).

All four cubes are exposed through **two shared views** (`student_grades_detail`
and `student_grades_summary`) using explicit `join_path:` blocks per cube. BI
tools filter to the cube they need via dimensions unique to each grain (e.g.,
`assignment_name` from `student_grades_assignments`, `gpa_term` from
`student_grades_gpa`). This is the same multi-cube pattern used in multi-grain
attendance queries.

---

## Task 1: `student_grades_term` cube

**Files:**

- Create: `src/cube/model/cubes/gradebook/student_grades_term.yml`

The cube inlines `dim_student_section_enrollments` (via
`student_section_enrollment_key`), `dim_course_sections` (via
`course_section_key`), `dim_courses` (via `course_key`), and
`bridge_course_section_teachers` (via `course_section_key`) directly in its
`sql:` block. This surfaces `teacher_staff_key` on the cube, enabling the join
to `staff` for teacher name. `bridge_course_section_teachers` carries
`effective_start_date` / `effective_end_date` for teacher assignment period —
use the section enrollment dates to filter to the primary teacher (choose the
teacher whose assignment period overlaps the enrollment period; in the SQL
block, take the first teacher row per section ordered by `effective_start_date`
to avoid fan-out).

- [ ] **Step 1: Write the cube file**

```yaml
cubes:
  - name: student_grades_term
    public: false
    sql: |
      SELECT
        gt.grades_term_key,
        gt.student_section_enrollment_key,
        gt.student_enrollment_key,
        gt.term_key,
        gt.term_start_date_key,
        gt.term_end_date_key,
        gt.academic_year,
        gt.percent_grade,
        gt.letter_grade,
        gt.percent_grade_adjusted,
        gt.letter_grade_adjusted,
        gt.citizenship_grade,
        gt.ytd_percent_grade,
        gt.ytd_percent_grade_adjusted,
        gt.ytd_letter_grade,
        gt.ytd_letter_grade_adjusted,
        gt.grade_points_earned,
        gt.ytd_grade_points,
        gt.potential_credit_hours,
        gt.last_grade_update_date,
        gt.is_excluded_from_gpa,
        sse.course_section_key,
        sse.entry_date          AS enrollment_entry_date,
        sse.exit_date           AS enrollment_exit_date,
        sse.is_dropped_section,
        sse.is_dropped_course,
        cs.course_key,
        cs.identifier           AS section_identifier,
        cs.period               AS section_period,
        c.course_code,
        c.course_title,
        c.credit_type,
        c.academic_subject,
        c.credits               AS course_credits,
        bct.staff_key           AS teacher_staff_key,
        bct.role                AS teacher_role
      FROM kipptaf_marts.fct_grades_term gt
      JOIN kipptaf_marts.dim_student_section_enrollments sse
        ON sse.student_section_enrollment_key = gt.student_section_enrollment_key
      JOIN kipptaf_marts.dim_course_sections cs
        ON cs.course_section_key = sse.course_section_key
      JOIN kipptaf_marts.dim_courses c
        ON c.course_key = cs.course_key
      LEFT JOIN (
        SELECT
          course_section_key,
          staff_key,
          role,
          effective_start_date,
          effective_end_date,
          ROW_NUMBER() OVER (
            PARTITION BY course_section_key
            ORDER BY effective_start_date
          ) AS rn
        FROM kipptaf_marts.bridge_course_section_teachers
      ) bct
        ON bct.course_section_key = sse.course_section_key
        AND bct.rn = 1

    joins:
      - name: terms
        sql: "{terms.term_key} = {CUBE}.term_key"
        relationship: many_to_one

      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

      - name: staff
        sql: "{staff.staff_key} = {CUBE}.teacher_staff_key"
        relationship: many_to_one

      - name: staff_reporting_relationships
        sql: >
          {staff_reporting_relationships.staff_key} = {CUBE}.teacher_staff_key
          AND CAST({CUBE}.term_start_date_key AS TIMESTAMP)
              BETWEEN CAST({staff_reporting_relationships.effective_start_date}
              AS TIMESTAMP)
              AND CAST({staff_reporting_relationships.effective_end_date}
              AS TIMESTAMP)
        relationship: many_to_one

      - name: staff_manager
        sql: >
          {staff_manager.staff_key} =
          {staff_reporting_relationships.manager_staff_key}
        relationship: many_to_one

    dimensions:
      - name: grades_term_key
        sql: grades_term_key
        type: string
        primary_key: true

      - name: term_start_date
        sql: CAST(term_start_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: academic_year
        sql: academic_year
        type: number
        public: true

      - name: course_code
        sql: course_code
        type: string
        public: true

      - name: course_title
        sql: course_title
        type: string
        public: true

      - name: credit_type
        sql: credit_type
        type: string
        public: true

      - name: academic_subject
        sql: academic_subject
        type: string
        public: true

      - name: course_credits
        sql: course_credits
        type: number
        public: true

      - name: section_identifier
        sql: section_identifier
        type: string
        public: true

      - name: section_period
        sql: section_period
        type: string
        public: true

      - name: teacher_staff_key
        sql: teacher_staff_key
        type: string
        public: true

      - name: teacher_role
        sql: teacher_role
        type: string
        public: true

      - name: percent_grade
        sql: percent_grade
        type: number
        public: true

      - name: letter_grade
        sql: letter_grade
        type: string
        public: true

      - name: percent_grade_adjusted
        sql: percent_grade_adjusted
        type: number
        public: true

      - name: letter_grade_adjusted
        sql: letter_grade_adjusted
        type: string
        public: true

      - name: citizenship_grade
        sql: citizenship_grade
        type: string
        public: true

      - name: ytd_percent_grade
        sql: ytd_percent_grade
        type: number
        public: true

      - name: ytd_letter_grade
        sql: ytd_letter_grade
        type: string
        public: true

      - name: ytd_letter_grade_adjusted
        sql: ytd_letter_grade_adjusted
        type: string
        public: true

      - name: grade_points_earned
        sql: grade_points_earned
        type: number
        public: true

      - name: potential_credit_hours
        sql: potential_credit_hours
        type: number
        public: true

      - name: is_excluded_from_gpa
        sql: is_excluded_from_gpa
        type: boolean
        public: true

      - name: is_dropped_section
        sql: is_dropped_section
        type: boolean
        public: true

      - name: is_dropped_course
        sql: is_dropped_course
        type: boolean
        public: true

    measures:
      - name: count_students
        description: Distinct students with a term grade record
        sql: student_enrollment_key
        type: count_distinct
        public: true

      - name: _sum_percent_grade
        sql: percent_grade
        type: sum
        public: false

      - name: _count_graded
        sql: "1"
        type: count
        public: false
        filters:
          - sql: "{CUBE}.percent_grade IS NOT NULL"

      - name: avg_percent_grade
        description: Average term percent grade across all section-term records
        sql: "{_sum_percent_grade} / NULLIF({_count_graded}, 0)"
        type: number
        format: percent
        public: true

      - name: count_failing
        description: >-
          Count of term grade records where the letter grade is F or F*
          (failing). Use with is_excluded_from_gpa = false for GPA-relevant
          failing courses.
        sql: grades_term_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.letter_grade IN ('F', 'F*')"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/gradebook/student_grades_term.yml').read_text()
)
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('join names:', [j['name'] for j in cube['joins']])
print('dimension count:', len(cube['dimensions']))
print('measure count:', len(cube['measures']))
"
```

Expected:

```text
cube name: student_grades_term
join names: ['terms', 'student_enrollments', 'staff', 'staff_reporting_relationships', 'staff_manager']
dimension count: 23
measure count: 5
```

- [ ] **Step 3: Run schema test**

```bash
uv run pytest tests/cube/test_cube_schema.py -v -k "gradebook"
```

Expected: `student_grades_term.yml` PASSES (no `dim_`/`fct_` prefix).

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/gradebook/student_grades_term.yml
git commit -m "feat(cube): add student_grades_term cube — term-level gradebook with inlined course/section/teacher"
```

---

## Task 2: `student_grades_category` cube

**Files:**

- Create: `src/cube/model/cubes/gradebook/student_grades_category.yml`

Same inline pattern as Task 1. `fct_grades_category` joins only via
`student_section_enrollment_key` (no `student_enrollment_key` FK). The `terms`
join uses the `term_key` FK that is nullable when a storecode does not map to a
reporting term.

- [ ] **Step 1: Write the cube file**

```yaml
cubes:
  - name: student_grades_category
    public: false
    sql: |
      SELECT
        gc.grades_category_key,
        gc.student_section_enrollment_key,
        gc.term_key,
        gc.academic_year,
        gc.type                 AS category_type,
        gc.order                AS category_order,
        gc.reporting_term,
        gc.quarter,
        gc.percent_grade,
        gc.citizenship_grade,
        gc.percent_grade_ytd_running,
        gc.is_current,
        sse.student_enrollment_key,
        sse.course_section_key,
        sse.entry_date          AS enrollment_entry_date,
        sse.exit_date           AS enrollment_exit_date,
        cs.course_key,
        cs.identifier           AS section_identifier,
        c.course_code,
        c.course_title,
        c.credit_type,
        c.academic_subject,
        bct.staff_key           AS teacher_staff_key,
        bct.role                AS teacher_role
      FROM kipptaf_marts.fct_grades_category gc
      JOIN kipptaf_marts.dim_student_section_enrollments sse
        ON sse.student_section_enrollment_key = gc.student_section_enrollment_key
      JOIN kipptaf_marts.dim_course_sections cs
        ON cs.course_section_key = sse.course_section_key
      JOIN kipptaf_marts.dim_courses c
        ON c.course_key = cs.course_key
      LEFT JOIN (
        SELECT
          course_section_key,
          staff_key,
          role,
          effective_start_date,
          effective_end_date,
          ROW_NUMBER() OVER (
            PARTITION BY course_section_key
            ORDER BY effective_start_date
          ) AS rn
        FROM kipptaf_marts.bridge_course_section_teachers
      ) bct
        ON bct.course_section_key = sse.course_section_key
        AND bct.rn = 1

    joins:
      - name: terms
        sql: "{terms.term_key} = {CUBE}.term_key"
        relationship: many_to_one

      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

      - name: staff
        sql: "{staff.staff_key} = {CUBE}.teacher_staff_key"
        relationship: many_to_one

      - name: staff_reporting_relationships
        sql: >
          {staff_reporting_relationships.staff_key} = {CUBE}.teacher_staff_key
          AND CAST({CUBE}.enrollment_entry_date AS TIMESTAMP)
              BETWEEN CAST({staff_reporting_relationships.effective_start_date}
              AS TIMESTAMP)
              AND CAST({staff_reporting_relationships.effective_end_date}
              AS TIMESTAMP)
        relationship: many_to_one

      - name: staff_manager
        sql: >
          {staff_manager.staff_key} =
          {staff_reporting_relationships.manager_staff_key}
        relationship: many_to_one

    dimensions:
      - name: grades_category_key
        sql: grades_category_key
        type: string
        primary_key: true

      - name: academic_year
        sql: academic_year
        type: number
        public: true

      - name: category_type
        sql: category_type
        type: string
        public: true

      - name: category_order
        sql: category_order
        type: string
        public: true

      - name: reporting_term
        sql: reporting_term
        type: string
        public: true

      - name: quarter
        sql: quarter
        type: string
        public: true

      - name: course_code
        sql: course_code
        type: string
        public: true

      - name: course_title
        sql: course_title
        type: string
        public: true

      - name: credit_type
        sql: credit_type
        type: string
        public: true

      - name: academic_subject
        sql: academic_subject
        type: string
        public: true

      - name: section_identifier
        sql: section_identifier
        type: string
        public: true

      - name: teacher_staff_key
        sql: teacher_staff_key
        type: string
        public: true

      - name: teacher_role
        sql: teacher_role
        type: string
        public: true

      - name: percent_grade
        sql: percent_grade
        type: number
        public: true

      - name: citizenship_grade
        sql: citizenship_grade
        type: string
        public: true

      - name: percent_grade_ytd_running
        sql: percent_grade_ytd_running
        type: number
        public: true

      - name: is_current
        sql: is_current
        type: boolean
        public: true

    measures:
      - name: count_students
        description: Distinct students with a category grade record
        sql: student_enrollment_key
        type: count_distinct
        public: true

      - name: _sum_percent_grade
        sql: percent_grade
        type: sum
        public: false

      - name: _count_graded
        sql: "1"
        type: count
        public: false
        filters:
          - sql: "{CUBE}.percent_grade IS NOT NULL"

      - name: avg_percent_grade
        description:
          Average category percent grade across all section-term-category
          records
        sql: "{_sum_percent_grade} / NULLIF({_count_graded}, 0)"
        type: number
        format: percent
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/gradebook/student_grades_category.yml').read_text()
)
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('join names:', [j['name'] for j in cube['joins']])
print('dimension count:', len(cube['dimensions']))
print('measure count:', len(cube['measures']))
"
```

Expected:

```text
cube name: student_grades_category
join names: ['terms', 'student_enrollments', 'staff', 'staff_reporting_relationships', 'staff_manager']
dimension count: 17
measure count: 4
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/cubes/gradebook/student_grades_category.yml
git commit -m "feat(cube): add student_grades_category cube — category-level gradebook with inlined course/section/teacher"
```

---

## Task 3: `student_grades_assignments` cube

**Files:**

- Create: `src/cube/model/cubes/gradebook/student_grades_assignments.yml`

`fct_grades_assignments` has `due_date_key` (DATE) as its event date FK to
`dim_dates`. It joins `dim_student_section_enrollments` via
`student_section_enrollment_key` — same inline pattern as Term and Category
cubes.

- [ ] **Step 1: Write the cube file**

```yaml
cubes:
  - name: student_grades_assignments
    public: false
    sql: |
      SELECT
        ga.grades_assignment_key,
        ga.student_section_enrollment_key,
        ga.student_enrollment_key,
        ga.term_key,
        ga.due_date_key,
        ga.academic_year,
        ga.name                       AS assignment_name,
        ga.category_name,
        ga.category_code,
        ga.points_earned,
        ga.numeric_grade_earned,
        ga.max_points,
        ga.score_percent,
        ga.is_missing,
        ga.is_late,
        ga.is_exempt,
        ga.is_expected,
        ga.is_counted_in_final_grade,
        sse.course_section_key,
        sse.entry_date                AS enrollment_entry_date,
        sse.exit_date                 AS enrollment_exit_date,
        cs.course_key,
        cs.identifier                 AS section_identifier,
        c.course_code,
        c.course_title,
        c.credit_type,
        c.academic_subject,
        bct.staff_key                 AS teacher_staff_key,
        bct.role                      AS teacher_role
      FROM kipptaf_marts.fct_grades_assignments ga
      JOIN kipptaf_marts.dim_student_section_enrollments sse
        ON sse.student_section_enrollment_key = ga.student_section_enrollment_key
      JOIN kipptaf_marts.dim_course_sections cs
        ON cs.course_section_key = sse.course_section_key
      JOIN kipptaf_marts.dim_courses c
        ON c.course_key = cs.course_key
      LEFT JOIN (
        SELECT
          course_section_key,
          staff_key,
          role,
          effective_start_date,
          effective_end_date,
          ROW_NUMBER() OVER (
            PARTITION BY course_section_key
            ORDER BY effective_start_date
          ) AS rn
        FROM kipptaf_marts.bridge_course_section_teachers
      ) bct
        ON bct.course_section_key = sse.course_section_key
        AND bct.rn = 1

    joins:
      - name: dates
        sql: "{dates.date_day} = CAST({CUBE}.due_date_key AS TIMESTAMP)"
        relationship: many_to_one

      - name: terms
        sql: "{terms.term_key} = {CUBE}.term_key"
        relationship: many_to_one

      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

      - name: staff
        sql: "{staff.staff_key} = {CUBE}.teacher_staff_key"
        relationship: many_to_one

      - name: staff_reporting_relationships
        sql: >
          {staff_reporting_relationships.staff_key} = {CUBE}.teacher_staff_key
          AND CAST({CUBE}.due_date_key AS TIMESTAMP)
              BETWEEN CAST({staff_reporting_relationships.effective_start_date}
              AS TIMESTAMP)
              AND CAST({staff_reporting_relationships.effective_end_date}
              AS TIMESTAMP)
        relationship: many_to_one

      - name: staff_manager
        sql: >
          {staff_manager.staff_key} =
          {staff_reporting_relationships.manager_staff_key}
        relationship: many_to_one

    dimensions:
      - name: grades_assignment_key
        sql: grades_assignment_key
        type: string
        primary_key: true

      - name: due_date
        sql: CAST(due_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: academic_year
        sql: academic_year
        type: number
        public: true

      - name: assignment_name
        sql: assignment_name
        type: string
        public: true

      - name: category_name
        sql: category_name
        type: string
        public: true

      - name: category_code
        sql: category_code
        type: string
        public: true

      - name: course_code
        sql: course_code
        type: string
        public: true

      - name: course_title
        sql: course_title
        type: string
        public: true

      - name: credit_type
        sql: credit_type
        type: string
        public: true

      - name: academic_subject
        sql: academic_subject
        type: string
        public: true

      - name: section_identifier
        sql: section_identifier
        type: string
        public: true

      - name: teacher_staff_key
        sql: teacher_staff_key
        type: string
        public: true

      - name: teacher_role
        sql: teacher_role
        type: string
        public: true

      - name: points_earned
        sql: points_earned
        type: number
        public: true

      - name: numeric_grade_earned
        sql: numeric_grade_earned
        type: number
        public: true

      - name: max_points
        sql: max_points
        type: number
        public: true

      - name: score_percent
        sql: score_percent
        type: number
        public: true

      - name: is_missing
        sql: is_missing
        type: boolean
        public: true

      - name: is_late
        sql: is_late
        type: boolean
        public: true

      - name: is_exempt
        sql: is_exempt
        type: boolean
        public: true

      - name: is_expected
        sql: is_expected
        type: boolean
        public: true

      - name: is_counted_in_final_grade
        sql: is_counted_in_final_grade
        type: boolean
        public: true

    measures:
      - name: count_students
        description: Distinct students with at least one assignment record
        sql: student_enrollment_key
        type: count_distinct
        public: true

      - name: count_assignments
        description: Total expected assignment records
        sql: grades_assignment_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.is_expected = true"

      - name: count_missing
        description: Count of expected assignments flagged as missing
        sql: grades_assignment_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.is_missing = true"
          - sql: "{CUBE}.is_expected = true"

      - name: pct_missing
        description: Percentage of expected assignments flagged as missing
        sql: "1.0 * {count_missing} / NULLIF({count_assignments}, 0)"
        type: number
        format: percent
        public: true

      - name: _sum_score_percent
        sql: score_percent
        type: sum
        public: false
        filters:
          - sql: "{CUBE}.is_counted_in_final_grade = true"
          - sql: "{CUBE}.score_percent IS NOT NULL"

      - name: _count_scored
        sql: "1"
        type: count
        public: false
        filters:
          - sql: "{CUBE}.is_counted_in_final_grade = true"
          - sql: "{CUBE}.score_percent IS NOT NULL"

      - name: avg_score_percent
        description: >-
          Average score percent across assignments counted in the final grade.
          Excludes missing, exempt, and unscored assignments.
        sql: "{_sum_score_percent} / NULLIF({_count_scored}, 0)"
        type: number
        format: percent
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/gradebook/student_grades_assignments.yml').read_text()
)
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('join names:', [j['name'] for j in cube['joins']])
print('dimension count:', len(cube['dimensions']))
print('measure count:', len(cube['measures']))
"
```

Expected:

```text
cube name: student_grades_assignments
join names: ['dates', 'terms', 'student_enrollments', 'staff', 'staff_reporting_relationships', 'staff_manager']
dimension count: 22
measure count: 7
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/cubes/gradebook/student_grades_assignments.yml
git commit -m "feat(cube): add student_grades_assignments cube — assignment-level gradebook with inlined course/section/teacher"
```

---

## Task 4: `student_grades_gpa` cube

**Files:**

- Create: `src/cube/model/cubes/gradebook/student_grades_gpa.yml`

`fct_grades_gpa` operates at the student enrollment × term grain — no section
key. It uses `sql_table:` (no inline joins needed). Joins only
`student_enrollments` and `terms` via direct FK. No teacher FK on this fact.

- [ ] **Step 1: Write the cube file**

```yaml
cubes:
  - name: student_grades_gpa
    public: false
    sql_table: kipptaf_marts.fct_grades_gpa

    joins:
      - name: terms
        sql: "{terms.term_key} = {CUBE}.term_key"
        relationship: many_to_one

      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

    dimensions:
      - name: grades_gpa_key
        sql: grades_gpa_key
        type: string
        primary_key: true

      - name: academic_year
        sql: academic_year
        type: number
        public: true

      - name: semester
        sql: semester
        type: string
        public: true

      - name: gpa_term
        sql: gpa_term
        type: number
        public: true

      - name: gpa_ytd
        sql: gpa_ytd
        type: number
        public: true

      - name: gpa_ytd_unweighted
        sql: gpa_ytd_unweighted
        type: number
        public: true

      - name: gpa_semester
        sql: gpa_semester
        type: number
        public: true

      - name: grade_avg_term
        sql: grade_avg_term
        type: number
        public: true

      - name: grade_avg_ytd
        sql: grade_avg_ytd
        type: number
        public: true

      - name: cumulative_gpa
        sql: cumulative_gpa
        type: number
        public: true

      - name: cumulative_gpa_unweighted
        sql: cumulative_gpa_unweighted
        type: number
        public: true

      - name: cumulative_gpa_projected
        sql: cumulative_gpa_projected
        type: number
        public: true

      - name: credit_hours_term
        sql: credit_hours_term
        type: number
        public: true

      - name: credit_hours_ytd
        sql: credit_hours_ytd
        type: number
        public: true

      - name: credit_hours_earned_cumulative
        sql: credit_hours_earned_cumulative
        type: number
        public: true

      - name: credit_hours_attempted_cumulative
        sql: credit_hours_attempted_cumulative
        type: number
        public: true

      - name: n_failing_ytd
        sql: n_failing_ytd
        type: number
        public: true

      - name: is_current
        sql: is_current
        type: boolean
        public: true

    measures:
      - name: count_students
        description: Distinct students with a GPA snapshot record
        sql: student_enrollment_key
        type: count_distinct
        public: true

      - name: _sum_gpa_ytd
        sql: gpa_ytd
        type: sum
        public: false

      - name: _count_gpa_ytd
        sql: "1"
        type: count
        public: false
        filters:
          - sql: "{CUBE}.gpa_ytd IS NOT NULL"

      - name: avg_gpa_ytd
        description:
          Average year-to-date weighted GPA across all student-term snapshots
        sql: "{_sum_gpa_ytd} / NULLIF({_count_gpa_ytd}, 0)"
        type: number
        public: true

      - name: _sum_cumulative_gpa
        sql: cumulative_gpa
        type: sum
        public: false

      - name: _count_cumulative_gpa
        sql: "1"
        type: count
        public: false
        filters:
          - sql: "{CUBE}.cumulative_gpa IS NOT NULL"

      - name: avg_cumulative_gpa
        description: >-
          Average cumulative weighted GPA across all student-term snapshots.
          Filter to is_current = true for the latest GPA state per student.
        sql: "{_sum_cumulative_gpa} / NULLIF({_count_cumulative_gpa}, 0)"
        type: number
        public: true

      - name: avg_n_failing_ytd
        description:
          Average count of failing courses per student across snapshots
        sql: n_failing_ytd
        type: avg
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/gradebook/student_grades_gpa.yml').read_text()
)
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('sql_table:', cube.get('sql_table'))
print('join names:', [j['name'] for j in cube['joins']])
print('dimension count:', len(cube['dimensions']))
print('measure count:', len(cube['measures']))
"
```

Expected:

```text
cube name: student_grades_gpa
sql_table: kipptaf_marts.fct_grades_gpa
join names: ['terms', 'student_enrollments']
dimension count: 18
measure count: 8
```

- [ ] **Step 3: Run full schema test — all four new cubes must pass**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all tests PASS including the four new gradebook cubes.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/gradebook/student_grades_gpa.yml
git commit -m "feat(cube): add student_grades_gpa cube — GPA periodic snapshot at student x term grain"
```

---

## Task 5: `student_grades_detail` view

**Files:**

- Create: `src/cube/model/views/gradebook/student_grades_detail.yml`

Detail view exposes all four cubes via separate `join_path:` blocks. Student PII
fields (`full_name`, `birth_date`, `lea_student_identifier`,
`state_student_identifier`) and staff PII fields (`staff_full_name`,
`staff_first_name`, `staff_last_name`, `staff_work_email`, `staff_google_email`,
`staff_personal_email`, `staff_personal_cell_phone`,
`staff_active_directory_username`, `staff_staff_unique_id`,
`staff_manager_full_name`, `staff_manager_first_name`,
`staff_manager_last_name`, `staff_manager_work_email`,
`staff_manager_google_email`, `staff_manager_personal_email`,
`staff_manager_personal_cell_phone`, `staff_manager_active_directory_username`,
`staff_manager_staff_unique_id`) are gated by their respective PII access
groups.

`prefix: true` on each join path means every field name in `includes:` becomes
`<join_path_last_segment>_<field_name>` in the view namespace. The
`access_policy` `excludes:` list must use post-prefix names.

- [ ] **Step 1: Write the view file**

```yaml
views:
  - name: student_grades_detail
    description: >-
      Row-level student gradebook. Combines four grains in one view — term
      grades (student_grades_term), category grades (student_grades_category),
      assignment scores (student_grades_assignments), and GPA snapshots
      (student_grades_gpa). Filter to the cube grain you need using dimensions
      unique to each: assignment_name for assignments, gpa_term / gpa_ytd for
      GPA, category_type / quarter for categories, percent_grade / letter_grade
      for term grades.

      Teacher and manager context comes from bridge_course_section_teachers
      inlined into the three section-grain cubes. The primary teacher per
      section (earliest effective_start_date) is surfaced; multi-teacher
      sections expose only one row. Manager resolves to the teacher's manager at
      the term start date (term cubes) or assignment due date (assignments cube)
      via staff_reporting_relationships.

      Contains direct student and staff identifiers — see access_policy for PII
      gating.

    cubes:
      - join_path: student_grades_term
        includes:
          - count_students
          - avg_percent_grade
          - count_failing
          - term_start_date
          - academic_year
          - course_code
          - course_title
          - credit_type
          - academic_subject
          - course_credits
          - section_identifier
          - section_period
          - teacher_staff_key
          - teacher_role
          - percent_grade
          - letter_grade
          - percent_grade_adjusted
          - letter_grade_adjusted
          - citizenship_grade
          - ytd_percent_grade
          - ytd_letter_grade
          - ytd_letter_grade_adjusted
          - grade_points_earned
          - potential_credit_hours
          - is_excluded_from_gpa
          - is_dropped_section
          - is_dropped_course

      - join_path: student_grades_term.terms
        prefix: true
        includes:
          - academic_year
          - semester
          - term_name
          - term_code
          - term_type

      - join_path: student_grades_term.student_enrollments
        prefix: true
        includes:
          - student_enrollment_key
          - grade_level
          - graduation_year

      - join_path: student_grades_term.student_enrollments.students
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

      - join_path: student_grades_term.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band

      - join_path: student_grades_term.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_grades_term.staff
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - work_email
          - google_email
          - personal_email
          - personal_cell_phone
          - active_directory_username
          - staff_unique_id

      - join_path: student_grades_term.staff_manager
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - work_email
          - google_email
          - personal_email
          - personal_cell_phone
          - active_directory_username
          - staff_unique_id

      - join_path: student_grades_category
        includes:
          - avg_percent_grade
          - academic_year
          - category_type
          - category_order
          - reporting_term
          - quarter
          - course_code
          - course_title
          - credit_type
          - academic_subject
          - section_identifier
          - teacher_staff_key
          - teacher_role
          - percent_grade
          - citizenship_grade
          - percent_grade_ytd_running
          - is_current

      - join_path: student_grades_assignments
        includes:
          - count_assignments
          - count_missing
          - pct_missing
          - avg_score_percent
          - due_date
          - academic_year
          - assignment_name
          - category_name
          - category_code
          - course_code
          - course_title
          - credit_type
          - academic_subject
          - section_identifier
          - teacher_staff_key
          - teacher_role
          - points_earned
          - numeric_grade_earned
          - max_points
          - score_percent
          - is_missing
          - is_late
          - is_exempt
          - is_expected
          - is_counted_in_final_grade

      - join_path: student_grades_gpa
        includes:
          - count_students
          - avg_gpa_ytd
          - avg_cumulative_gpa
          - avg_n_failing_ytd
          - academic_year
          - semester
          - gpa_term
          - gpa_ytd
          - gpa_ytd_unweighted
          - gpa_semester
          - grade_avg_term
          - grade_avg_ytd
          - cumulative_gpa
          - cumulative_gpa_unweighted
          - cumulative_gpa_projected
          - credit_hours_term
          - credit_hours_ytd
          - credit_hours_earned_cumulative
          - credit_hours_attempted_cumulative
          - n_failing_ytd
          - is_current

    meta:
      folders:
        - name: Term Grades
          members:
            - term_start_date
            - academic_year
            - percent_grade
            - letter_grade
            - percent_grade_adjusted
            - letter_grade_adjusted
            - citizenship_grade
            - ytd_percent_grade
            - ytd_letter_grade
            - ytd_letter_grade_adjusted
            - grade_points_earned
            - potential_credit_hours
            - is_excluded_from_gpa
            - is_dropped_section
            - is_dropped_course
        - name: Category Grades
          members:
            - category_type
            - category_order
            - reporting_term
            - quarter
            - is_current
        - name: Assignment Scores
          members:
            - due_date
            - assignment_name
            - category_name
            - category_code
            - points_earned
            - numeric_grade_earned
            - max_points
            - score_percent
            - is_missing
            - is_late
            - is_exempt
            - is_expected
            - is_counted_in_final_grade
        - name: GPA
          members:
            - semester
            - gpa_term
            - gpa_ytd
            - gpa_ytd_unweighted
            - gpa_semester
            - grade_avg_term
            - grade_avg_ytd
            - cumulative_gpa
            - cumulative_gpa_unweighted
            - cumulative_gpa_projected
            - credit_hours_term
            - credit_hours_ytd
            - credit_hours_earned_cumulative
            - credit_hours_attempted_cumulative
            - n_failing_ytd
        - name: Course
          members:
            - course_code
            - course_title
            - credit_type
            - academic_subject
            - course_credits
            - section_identifier
            - section_period
            - teacher_staff_key
            - teacher_role
        - name: Term
          members:
            - terms_academic_year
            - terms_semester
            - terms_term_name
            - terms_term_code
            - terms_term_type
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
        - name: Enrollment
          members:
            - student_enrollments_student_enrollment_key
            - student_enrollments_grade_level
            - student_enrollments_graduation_year
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - regions_region_name
            - regions_state
        - name: Teacher
          members:
            - staff_staff_key
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            - staff_google_email
        - name: Manager
          members:
            - staff_manager_staff_key
            - staff_manager_full_name
            - staff_manager_first_name
            - staff_manager_last_name
            - staff_manager_work_email
            - staff_manager_google_email

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            # Student PII
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
            # Staff (teacher) PII
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            - staff_google_email
            - staff_personal_email
            - staff_personal_cell_phone
            - staff_active_directory_username
            - staff_staff_unique_id
            # Staff (manager) PII
            - staff_manager_full_name
            - staff_manager_first_name
            - staff_manager_last_name
            - staff_manager_work_email
            - staff_manager_google_email
            - staff_manager_personal_email
            - staff_manager_personal_cell_phone
            - staff_manager_active_directory_username
            - staff_manager_staff_unique_id
      - group: cube-access-student-pii
        member_level:
          includes: "*"
          excludes:
            # Student PII is unlocked by cube-access-student-pii.
            # Staff PII still requires cube-access-staff-pii.
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            - staff_google_email
            - staff_personal_email
            - staff_personal_cell_phone
            - staff_active_directory_username
            - staff_staff_unique_id
            - staff_manager_full_name
            - staff_manager_first_name
            - staff_manager_last_name
            - staff_manager_work_email
            - staff_manager_google_email
            - staff_manager_personal_email
            - staff_manager_personal_cell_phone
            - staff_manager_active_directory_username
            - staff_manager_staff_unique_id
      - group: cube-access-staff-pii
        member_level:
          includes: "*"
          excludes:
            # Staff PII is unlocked by cube-access-staff-pii.
            # Student PII still requires cube-access-student-pii.
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/views/gradebook/student_grades_detail.yml').read_text()
)
view = data['views'][0]
print('view name:', view['name'])
print('cube join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected:

```text
view name: student_grades_detail
cube join paths: ['student_grades_term', 'student_grades_term.terms', 'student_grades_term.student_enrollments', 'student_grades_term.student_enrollments.students', 'student_grades_term.student_enrollments.locations', 'student_grades_term.student_enrollments.locations.regions', 'student_grades_term.staff', 'student_grades_term.staff_manager', 'student_grades_category', 'student_grades_assignments', 'student_grades_gpa']
access groups: ['detail-access', 'cube-access-student-pii', 'cube-access-staff-pii']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/views/gradebook/student_grades_detail.yml
git commit -m "feat(cube): add student_grades_detail view — all four gradebook grains with student+staff PII gating"
```

---

## Task 6: `student_grades_summary` view

**Files:**

- Create: `src/cube/model/views/gradebook/student_grades_summary.yml`

Summary view has no individual identifiers — no `student_key`, no `staff_key`,
no names, no DOBs, no direct identifiers. Demographic dimensions
(`gender_identity`, `race`, `is_gifted`) are present as aggregate breakdowns.
Single `summary-access` policy block.

- [ ] **Step 1: Write the view file**

```yaml
views:
  - name: student_grades_summary
    description: >-
      Aggregated student gradebook. Combines four grains — term grades, category
      grades, assignment scores, and GPA snapshots. No direct student or staff
      identifiers. Demographic dimensions (gender_identity, race, is_gifted) are
      aggregate breakdowns only, not individual identifiers.

      Filter to the grain you need using dimensions unique to each cube:
      assignment_name / category_name for assignment-level, category_type /
      quarter for category-level, percent_grade / letter_grade for term-level,
      gpa_term / cumulative_gpa for GPA-level.

      Teacher identity is not exposed in this view. Course and subject
      breakdowns (course_title, academic_subject, credit_type) are available for
      aggregate analysis. Manager information is not exposed.

    cubes:
      - join_path: student_grades_term
        includes:
          - count_students
          - avg_percent_grade
          - count_failing
          - academic_year
          - course_code
          - course_title
          - credit_type
          - academic_subject
          - letter_grade
          - letter_grade_adjusted
          - citizenship_grade
          - ytd_letter_grade
          - ytd_letter_grade_adjusted
          - is_excluded_from_gpa
          - is_dropped_section
          - is_dropped_course

      - join_path: student_grades_term.terms
        prefix: true
        includes:
          - academic_year
          - semester
          - term_name
          - term_code
          - term_type

      - join_path: student_grades_term.student_enrollments
        prefix: true
        includes:
          - grade_level
          - graduation_year

      - join_path: student_grades_term.student_enrollments.students
        prefix: true
        includes:
          - gender_identity
          - race
          - is_gifted

      - join_path: student_grades_term.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band

      - join_path: student_grades_term.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_grades_category
        includes:
          - avg_percent_grade
          - academic_year
          - category_type
          - category_order
          - reporting_term
          - quarter
          - course_code
          - course_title
          - credit_type
          - academic_subject
          - citizenship_grade
          - is_current

      - join_path: student_grades_assignments
        includes:
          - count_assignments
          - count_missing
          - pct_missing
          - avg_score_percent
          - academic_year
          - category_name
          - category_code
          - course_code
          - course_title
          - credit_type
          - academic_subject
          - is_missing
          - is_late
          - is_exempt
          - is_counted_in_final_grade

      - join_path: student_grades_gpa
        includes:
          - count_students
          - avg_gpa_ytd
          - avg_cumulative_gpa
          - avg_n_failing_ytd
          - academic_year
          - semester
          - gpa_ytd_unweighted
          - cumulative_gpa_unweighted
          - credit_hours_earned_cumulative
          - credit_hours_attempted_cumulative
          - n_failing_ytd
          - is_current

    meta:
      folders:
        - name: Term Grades
          members:
            - academic_year
            - letter_grade
            - letter_grade_adjusted
            - citizenship_grade
            - ytd_letter_grade
            - ytd_letter_grade_adjusted
            - is_excluded_from_gpa
            - is_dropped_section
            - is_dropped_course
        - name: Category Grades
          members:
            - category_type
            - category_order
            - reporting_term
            - quarter
            - is_current
        - name: Assignment Scores
          members:
            - category_name
            - category_code
            - is_missing
            - is_late
            - is_exempt
            - is_counted_in_final_grade
        - name: GPA
          members:
            - semester
            - gpa_ytd_unweighted
            - cumulative_gpa_unweighted
            - credit_hours_earned_cumulative
            - credit_hours_attempted_cumulative
            - n_failing_ytd
        - name: Course
          members:
            - course_code
            - course_title
            - credit_type
            - academic_subject
        - name: Term
          members:
            - terms_academic_year
            - terms_semester
            - terms_term_name
            - terms_term_code
            - terms_term_type
        - name: Student
          members:
            - students_gender_identity
            - students_race
            - students_is_gifted
        - name: Enrollment
          members:
            - student_enrollments_grade_level
            - student_enrollments_graduation_year
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - regions_region_name
            - regions_state

    access_policy:
      # No PII tier — view contains no direct student or staff identifiers.
      # Demographic dimensions (race, gender_identity, is_gifted) are
      # aggregate breakdowns only.
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
    Path('src/cube/model/views/gradebook/student_grades_summary.yml').read_text()
)
view = data['views'][0]
print('view name:', view['name'])
print('access groups:', [p['group'] for p in view['access_policy']])
print('cube join paths:', [c['join_path'] for c in view['cubes']])
"
```

Expected:

```text
view name: student_grades_summary
access groups: ['summary-access']
cube join paths: ['student_grades_term', 'student_grades_term.terms', 'student_grades_term.student_enrollments', 'student_grades_term.student_enrollments.students', 'student_grades_term.student_enrollments.locations', 'student_grades_term.student_enrollments.locations.regions', 'student_grades_category', 'student_grades_assignments', 'student_grades_gpa']
```

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/gradebook/student_grades_summary.yml
git commit -m "feat(cube): add student_grades_summary view — all four gradebook grains, no PII, summary-access only"
```

---

## Implementation Notes

### Location filter dependency in multi-cube views

`student_grades_detail` and `student_grades_summary` expose location and region
context only through the `student_grades_term` join path:

```yaml
- join_path: student_grades_term.student_enrollments.locations
- join_path: student_grades_term.student_enrollments.locations.regions
```

`queryRewrite` injects a `locations.abbreviation` or `locations.region_key`
filter based on the user's scope group. **If an analyst queries only members
from `student_grades_category`, `student_grades_assignments`, or
`student_grades_gpa` join paths without including any `student_grades_term`
member, Cube cannot resolve the location join and the `queryRewrite` filter will
error or be silently skipped.**

In practice this is unlikely — most gradebook queries include at least one
term-grain dimension (academic_year, term_name, letter_grade). But queries that
request only GPA dimensions without any term context should always add
`student_grades_term.student_enrollments.locations` members (even just
`locations_abbreviation`) to anchor the location filter.

This is a structural constraint of the multi-cube view pattern. Resolving it
would require adding a `locations` join directly on `student_grades_gpa`,
`student_grades_category`, and `student_grades_assignments` — a scope increase
that is deferred to a follow-up once the usage pattern is clear.

### `student_grades_gpa` — snapshot aggregation risk

`gpa_ytd` and `cumulative_gpa` are **cumulative running snapshots** — one row
per student per term, restamped with the YTD value through that term. They are
NOT additive. `avg_gpa_ytd` and `avg_cumulative_gpa` average across all
snapshots in scope, so querying without filtering to a single term (or
`is_current = true`) averages redundant snapshots for students with multiple
terms.

The correct usage pattern depends on the question:

- **"What is each student's current GPA?"** → filter `is_current = true`
- **"What was average GPA at the end of Fall 2024?"** → filter
  `terms_term_code = 'F24'` (or equivalent)
- **"How has average GPA trended by term?"** → group by `terms_term_name`, no
  `is_current` filter — each term is a distinct snapshot

Querying `avg_gpa_ytd` with no term filter and no `is_current` filter will
average across ALL snapshots for ALL terms in scope, producing a meaningless
weighted mean across periods.

`student_grades_gpa` is a candidate for the `SNAPSHOT_CUBES` / snapshot anchor
pattern (`is_current` as the year-end flag). However, the gradebook snapshot
grain is per-term, not per-day, so the daily auto-injection mechanism does not
apply. The `is_current` filter serves the same purpose but must be applied
manually. Document this in the view description when implementing.

---

## Validation in Cube Cloud

After all tasks are committed and pushed, validate the changes in Cube Cloud Dev
Mode. Add the branch by name in Cube Cloud → Data Model → Dev Mode.

**Check 1 — Model loads:**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["student_grades_summary.count_students"],"limit":1}}' \
  | jq '.sql'
```

Expected: a SQL string with `fct_grades_term` appearing in the FROM clause (or
its inline SQL subquery).

**Check 2 — New view names appear in meta:**

The Cube MCP `meta` tool should list `student_grades_detail` and
`student_grades_summary` under views.

**Check 3 — Security gate works:**

Compile a query with a user who has no scope group — the SQL should contain
`WHERE (1 = 0)`:

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-for-user-with-no-scope-group>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["student_grades_summary.count_students"],"limit":1}}' \
  | jq '.sql' | grep -c "1 = 0"
```

Expected: `1`.

**Check 4 — Student PII is gated:**

Compile a query including `students_full_name` with a `detail-access` user (no
`cube-access-student-pii`) — the field should be absent from the result columns:

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-detail-access-no-pii>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"dimensions":["student_grades_detail.students_full_name"],"limit":1}}' \
  | jq '.error // .sql'
```

Expected: an error referencing "hidden member" or an empty result — not a full
name value.

**Check 5 — Staff PII is gated independently:**

Same pattern as Check 4 but for `staff_full_name` — verify staff PII is hidden
from users without `cube-access-staff-pii` even when they have
`cube-access-student-pii`.
