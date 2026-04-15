# Assessment Domain Implementation Plan

**Goal:** Build the assessment domain — dimensions covering assessment
definitions, comparison benchmarks, performance targets, and student
expectations, plus two fact tables scoped by whether scores link to enrollment
or to the student directly.

**Architecture:** `dim_assessments` is the central assessment reference
dimension, shared by both fact tables. `fct_assessment_scores_enrollment_scoped`
covers internal (Illuminate) and state assessments;
`fct_assessment_scores_student_scoped` covers college-entrance and AP
assessments. `dim_student_assessment_expectations` is the expectation scaffold
for internal assessments only. `dim_assessment_comparisons` and
`dim_assessment_targets` are standalone reference dims joinable to fact tables
via business keys.

**Tech Stack:** dbt (BigQuery dialect), `dbt_utils.generate_surrogate_key()`,
`dbt_utils.deduplicate()`.

**Spec reference:**
`docs/superpowers/specs/2026-03-27-star-schema-data-mart-design.md` — Assessment
Domain section.

**Dependencies:** Plan 1 (Conformed Dimensions), Plan 2 (Student Domain).

---

## Prerequisites

- Working directory:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-star-schema-data-mart/`
- All file paths relative to `src/dbt/kipptaf/`

## Task Overview

| Task | Model                                     | Type      | Dependencies |
| ---- | ----------------------------------------- | --------- | ------------ |
| 1    | `dim_assessments`                         | dimension | none         |
| 2    | `dim_assessment_comparisons`              | dimension | none         |
| 3    | `dim_assessment_targets`                  | dimension | none         |
| 4    | `dim_student_assessment_expectations`     | dimension | Task 1       |
| 5    | `fct_assessment_scores_enrollment_scoped` | fact      | Task 1       |
| 6    | `fct_assessment_scores_student_scoped`    | fact      | Task 1       |

---

### Task 1: `dim_assessments`

**Files:**

- `models/marts/dimensions/dim_assessments.sql`
- `models/marts/dimensions/properties/dim_assessments.yml`

**Spec grain:** One row per unique assessment definition across all source
systems (Illuminate internal, NJ state, FL state, college-entrance, AP).

**Key:** `assessment_key` =
`generate_surrogate_key(["assessment_type", "title", "subject_area", "scope", "module_code", "grade_level"])`.

**Upstream:**

- `int_assessments__assessments` (Illuminate internal)
- `int_pearson__all_assessments` (NJ state NJSLA/NJGPA)
- `int_fldoe__all_assessments` (FL state FAST)
- `int_assessments__college_assessment` (SAT, ACT, PSAT)
- `int_assessments__ap_assessments` (AP exams)

`DISTINCT` is used across all branches because upstream models are at the
student-score grain, not the assessment-definition grain.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 2: `dim_assessment_comparisons`

**Files:**

- `models/marts/dimensions/dim_assessment_comparisons.sql`
- `models/marts/dimensions/properties/dim_assessment_comparisons.yml`

**Spec grain:** One row per test_code x academic_year x region. Pivots
comparison entity rows (City, State, Neighborhood Schools) into columns.

**Key:** `assessment_comparison_key` =
`generate_surrogate_key(["academic_year", "test_name", "test_code", "region"])`.

**FKs:** `region_key` → `dim_regions`.

**Upstream:** `stg_google_sheets__state_test_comparison`.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 3: `dim_assessment_targets`

**Files:**

- `models/marts/dimensions/dim_assessment_targets.sql`
- `models/marts/dimensions/properties/dim_assessment_targets.yml`

**Spec grain:** One row per academic_year x school_id x state_assessment_code x
grade_level x illuminate_subject_area.

**Key:** `assessment_target_key` =
`generate_surrogate_key(["academic_year", "school_id", "state_assessment_code", "grade_level", "illuminate_subject_area"])`.

**FKs:** `location_key` → `dim_locations` (derived from `location_clean_name`).

**Upstream:** `stg_google_sheets__assessments__academic_goals` joined to
`stg_powerschool__schools` (for school_level and region).
`dbt_utils.deduplicate()` deduplicates on the grain, keeping the row with the
highest school_goal.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 4: `dim_student_assessment_expectations`

**Files:**

- `models/marts/dimensions/dim_student_assessment_expectations.sql`
- `models/marts/dimensions/properties/dim_student_assessment_expectations.yml`

**Spec grain:** One row per student x internal assessment x administration date.
Illuminate assessments only.

**Key:** `student_assessment_expectation_key` =
`generate_surrogate_key(["powerschool_student_number", "assessment_id", "administered_at"])`.

**FKs:**

- `assessment_key` → `dim_assessments`
- `term_key` → `dim_terms` (joined via `stg_google_sheets__reporting__terms` on
  administered_at between term dates; null when no matching reporting term)

**Upstream:** `int_assessments__scaffold` (student-assessment scaffold).

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 5: `fct_assessment_scores_enrollment_scoped`

**Files:**

- `models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`
- `models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`

**Spec grain:** One row per student x assessment x administration. Covers
internal Illuminate assessments and NJ/FL state assessments.

**Key:** `assessment_score_key` — surrogate derived from student + assessment +
response identifiers (varies by source).

**FKs:**

- `assessment_key` → `dim_assessments`
- `student_key` → `dim_students`
- `test_date_key` → `dim_dates` (null for state assessments with no specific
  date)

**Note:** FL state assessments carry only `state_student_id` (no
`student_number`). The `student_key` is derived from whichever identifier is
available.

**Upstream:**

- `int_assessments__response_rollup` (internal, deduplicated by
  `dbt_utils.deduplicate()`)
- `int_pearson__all_assessments` (NJ state)
- `int_fldoe__all_assessments` (FL state)

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 6: `fct_assessment_scores_student_scoped`

**Files:**

- `models/marts/facts/fct_assessment_scores_student_scoped.sql`
- `models/marts/facts/properties/fct_assessment_scores_student_scoped.yml`

**Spec grain:** One row per student x assessment x test date (or academic year
for AP). Covers SAT, ACT, PSAT, and AP exams.

**Key:** `assessment_score_key` — surrogate from student + score_type +
test_date

- rn_highest (college) or student + ap_course_name + academic_year + rn_highest
  (AP).

**FKs:**

- `student_key` → `dim_students`
- `assessment_key` → `dim_assessments`
- `test_date_key` → `dim_dates` (null for AP exams)

**Upstream:**

- `int_assessments__college_assessment` (deduplicated by
  `dbt_utils.deduplicate()`)
- `int_assessments__ap_assessments`

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

## Verification checklist

- [x] `dim_assessments` covers all 5 source branches with `DISTINCT` dedup
- [x] `assessment_scope` column distinguishes enrollment-scoped from
      student-scoped assessments
- [x] Both fact tables share the same `assessment_key` derivation as
      `dim_assessments`
- [x] `fct_assessment_scores_enrollment_scoped` handles null `student_number`
      for FL state assessments
- [x] `fct_assessment_scores_student_scoped` handles null `test_date_key` for AP
- [x] All uniqueness tests pass on primary keys
