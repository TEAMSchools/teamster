# Gradebook Domain Implementation Plan

**Goal:** Build the gradebook domain — four fact tables covering term grades,
category grades, individual assignment scores, and GPA snapshots. No new
dimensions are required; this domain joins to conformed dimensions and student
domain dims built in earlier plans.

**Architecture:** All four fact tables FK to `dim_student_section_enrollments`
(section-level) and/or `dim_student_enrollments` (year-level) from Plan 2.
`fct_grades_term` and `fct_grades_assignments` also FK to
`dim_student_enrollments`. `fct_grades_gpa` operates at the enrollment level
only. All four join to `dim_terms` via `stg_google_sheets__reporting__terms`
quarter-type terms. Date role-playing FKs link to `dim_dates` where applicable.

**Tech Stack:** dbt (BigQuery dialect), `dbt_utils.generate_surrogate_key()`,
`union_dataset_join_clause()` macro, PowerSchool union sources.

**Spec reference:**
`docs/superpowers/specs/2026-03-27-star-schema-data-mart-design.md` — Gradebook
Domain section.

**Dependencies:** Plan 1 (Conformed Dimensions), Plan 2 (Student + Course
Domains for `dim_student_enrollments` and `dim_student_section_enrollments`).

---

## Prerequisites

- Working directory:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-star-schema-data-mart/`
- All file paths relative to `src/dbt/kipptaf/`

## Task Overview

| Task | Model                    | Type | Dependencies    |
| ---- | ------------------------ | ---- | --------------- |
| 1    | `fct_grades_term`        | fact | Plan 2 complete |
| 2    | `fct_grades_category`    | fact | Plan 2 complete |
| 3    | `fct_grades_assignments` | fact | Plan 2 complete |
| 4    | `fct_grades_gpa`         | fact | Plan 2 complete |

---

### Task 1: `fct_grades_term`

**Files:**

- `models/marts/facts/fct_grades_term.sql`
- `models/marts/facts/properties/fct_grades_term.yml`

**Spec grain:** One row per student x section enrollment x term (storecode).

**Key:** `grades_term_key` =
`generate_surrogate_key(["cc_dcid", "_dbt_source_relation", "storecode"])`.

**FKs:**

- `student_section_enrollment_key` → `dim_student_section_enrollments`
- `student_enrollment_key` → `dim_student_enrollments`
- `term_key` → `dim_terms` (joined via storecode + school_id + region + yearid;
  null when storecode does not map to a reporting term)
- `term_start_date_key` → `dim_dates` (role-playing)
- `term_end_date_key` → `dim_dates` (role-playing)

**Upstream:**

- `base_powerschool__final_grades` (term and Y1 grade records)
- `base_powerschool__student_enrollments` (entrydate context for enrollment FK)
- `stg_google_sheets__reporting__terms` (quarter-type terms only)

**Key columns:** `percent_grade`, `letter_grade`, `percent_grade_adjusted`,
`letter_grade_adjusted`, `citizenship`, `y1_percent_grade`,
`y1_percent_grade_adjusted`, `y1_letter_grade`, `y1_letter_grade_adjusted`,
`grade_points`, `y1_grade_points`, `potential_credit_hours`, `exclude_from_gpa`.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 2: `fct_grades_category`

**Files:**

- `models/marts/facts/fct_grades_category.sql`
- `models/marts/facts/properties/fct_grades_category.yml`

**Spec grain:** One row per student x section enrollment x term x category type
(storecode + storecode_type combination).

**Key:** `grades_category_key` =
`generate_surrogate_key(["cc_dcid", "_dbt_source_relation", "storecode", "storecode_type"])`.

**FKs:**

- `student_section_enrollment_key` → `dim_student_section_enrollments`
- `term_key` → `dim_terms` (null when storecode does not map)

**Upstream:**

- `int_powerschool__category_grades` (per-category grade records)
- `base_powerschool__course_enrollments` (cc_dcid + source relation)
- `stg_google_sheets__reporting__terms` (quarter-type terms)

**Key columns:** `category_type` (Q/E), `category_order`, `reporting_term`,
`quarter`, `percent_grade`, `citizenship_grade`, `percent_grade_y1_running`,
`is_current`.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 3: `fct_grades_assignments`

**Files:**

- `models/marts/facts/fct_grades_assignments.sql`
- `models/marts/facts/properties/fct_grades_assignments.yml`

**Spec grain:** One row per student x assignment (assignmentsectionid x
students_dcid).

**Key:** `grades_assignment_key` =
`generate_surrogate_key(["assignmentsectionid", "_dbt_source_relation", "students_dcid"])`.

**FKs:**

- `student_section_enrollment_key` → `dim_student_section_enrollments`
- `student_enrollment_key` → `dim_student_enrollments`
- `term_key` → `dim_terms` (joined by due_date between term start/end; null when
  due_date falls outside all reporting terms)
- `due_date_key` → `dim_dates` (role-playing)

**Upstream:**

- `int_powerschool__gradebook_assignments_scores` (assignment scores)
- `base_powerschool__course_enrollments` (section enrollment context)
- `base_powerschool__student_enrollments` (year enrollment — assignment must
  fall within entrydate/exitdate)
- `stg_google_sheets__reporting__terms` (quarter-type terms)

**Key columns:** `assignment_name`, `category_name`, `category_code`,
`score_type`, `score`, `points_possible`, `score_percent`, `is_missing`,
`is_late`, `is_exempt`, `is_expected`, `is_counted_in_final_grade`.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 4: `fct_grades_gpa`

**Files:**

- `models/marts/facts/fct_grades_gpa.sql`
- `models/marts/facts/properties/fct_grades_gpa.yml`

**Spec grain:** One row per student enrollment x term (periodic GPA snapshot).

**Key:** `grades_gpa_key` =
`generate_surrogate_key(["studentid", "_dbt_source_relation", "yearid", "term_name"])`.

**FKs:**

- `student_enrollment_key` → `dim_student_enrollments` (rn_year = 1)
- `term_key` → `dim_terms` (null when term_name does not map)

**Upstream:**

- `int_powerschool__gpa_term` (term and Y1 GPA)
- `int_powerschool__gpa_cumulative` (cumulative GPA across all years)
- `base_powerschool__student_enrollments` (enrollment FK, rn_year = 1)
- `stg_google_sheets__reporting__terms` (quarter-type terms)

**Key columns:** `gpa_term`, `gpa_y1`, `gpa_y1_unweighted`, `gpa_semester`,
`grade_avg_term`, `grade_avg_y1`, `cumulative_y1_gpa`,
`cumulative_y1_gpa_unweighted`, `cumulative_y1_gpa_projected`,
`credit_hours_term`, `credit_hours_y1`, `credit_hours_earned_cumulative`,
`credit_hours_attempted_cumulative`, `n_failing_y1`, `is_current_term`,
`is_current_row`.

`is_current_row` is TRUE for the most recent snapshot per student x school, used
to collapse to the latest GPA state.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

## Verification checklist

- [x] All four fact tables FK to `dim_student_section_enrollments` or
      `dim_student_enrollments` (as appropriate to grain)
- [x] `term_key` derivation is consistent across all four models (same
      `generate_surrogate_key` field list)
- [x] `union_dataset_join_clause()` used in all union model joins
- [x] `fct_grades_gpa.is_current_row` correctly identifies one row per student x
      school
- [x] All uniqueness tests pass on primary keys
