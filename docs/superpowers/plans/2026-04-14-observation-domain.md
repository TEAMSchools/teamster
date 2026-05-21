# Observation Domain Implementation Plan

**Goal:** Build the staff observation domain — dimensions covering rubric
definitions, measurement items, observation types, microgoal taxonomy, and
observation expectations, plus three fact tables for observation events, item
scores, and microgoal assignments.

**Architecture:** `dim_staff_observation_rubrics` →
`dim_staff_observation_rubric_measurements` form a two-level rubric hierarchy.
`fct_staff_observations` is the primary observation event fact; its child
`fct_staff_observation_scores` captures per-measurement item scores.
`fct_staff_observation_microgoals` covers microgoal assignments — a separate
SchoolMint Grow concept. `dim_staff_observation_expectations` is the scaffold
for expected observation coverage.

**Tech Stack:** dbt (BigQuery dialect), `dbt_utils.generate_surrogate_key()`,
`dbt_utils.deduplicate()`, SchoolMint Grow source (`stg_schoolmint_grow__*`).

**Spec reference:**
`docs/superpowers/specs/2026-03-27-star-schema-data-mart-design.md` —
Observation Domain section.

**Dependencies:** Plan 1 (Conformed Dimensions), Plan 3 (Staff Domain for
dim_staff and dim_terms).

---

## Prerequisites

- Working directory:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-star-schema-data-mart/`
- All file paths relative to `src/dbt/kipptaf/`

## Task Overview

| Task | Model                                       | Type      | Dependencies |
| ---- | ------------------------------------------- | --------- | ------------ |
| 1    | `dim_staff_observation_rubrics`             | dimension | none         |
| 2    | `dim_staff_observation_rubric_measurements` | dimension | Task 1       |
| 3    | `dim_staff_observation_types`               | dimension | none         |
| 4    | `dim_staff_observation_microgoal_types`     | dimension | none         |
| 5    | `dim_staff_observation_expectations`        | dimension | none         |
| 6    | `fct_staff_observations`                    | fact      | Tasks 1-3    |
| 7    | `fct_staff_observation_scores`              | fact      | Tasks 1-2, 6 |
| 8    | `fct_staff_observation_microgoals`          | fact      | Task 4       |

---

### Task 1: `dim_staff_observation_rubrics`

**Files:**

- `models/marts/dimensions/dim_staff_observation_rubrics.sql`
- `models/marts/dimensions/properties/dim_staff_observation_rubrics.yml`

**Spec grain:** One row per SchoolMint Grow rubric definition.

**Key:** `staff_observation_rubric_key` =
`generate_surrogate_key(["rubric_id"])`.

**Upstream:** `stg_schoolmint_grow__rubrics__measurement_groups__measurements`.
`dbt_utils.deduplicate()` deduplicates on `rubric_id` ordered by
`last_modified desc` (one row per rubric, latest modification wins).

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 2: `dim_staff_observation_rubric_measurements`

**Files:**

- `models/marts/dimensions/dim_staff_observation_rubric_measurements.sql`
- `models/marts/dimensions/properties/dim_staff_observation_rubric_measurements.yml`

**Spec grain:** One row per measurement item per rubric.

**Key:** `staff_observation_rubric_measurement_key` =
`generate_surrogate_key(["rubric_id", "measurement_id"])`.

**FKs:** `staff_observation_rubric_key` → `dim_staff_observation_rubrics`.

**Upstream:**

- `stg_schoolmint_grow__rubrics__measurement_groups__measurements` (strand and
  weight context)
- `stg_schoolmint_grow__measurements` (measurement name, description, scale)

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 3: `dim_staff_observation_types`

**Files:**

- `models/marts/dimensions/dim_staff_observation_types.sql`
- `models/marts/dimensions/properties/dim_staff_observation_types.yml`

**Spec grain:** One row per observation type defined as a non-archived
`observationtypes` generic tag in SchoolMint Grow.

**Key:** `staff_observation_type_key` = `generate_surrogate_key(["tag_id"])`.

**Upstream:** `stg_schoolmint_grow__generic_tags` filtered to
`tag_type = 'observationtypes' AND archived_at IS NULL`.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 4: `dim_staff_observation_microgoal_types`

**Files:**

- `models/marts/dimensions/dim_staff_observation_microgoal_types.sql`
- `models/marts/dimensions/properties/dim_staff_observation_microgoal_types.yml`

**Spec grain:** One row per leaf-level goal in the SchoolMint Grow 4-level
taxonomy (goal_type > bucket > strand > goal).

**Key:** `staff_observation_microgoal_type_key` =
`generate_surrogate_key(["tag_id"])`.

**Upstream:** `int_schoolmint_grow__microgoals` (pre-built taxonomy intermediate
model).

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 5: `dim_staff_observation_expectations`

**Files:**

- `models/marts/dimensions/dim_staff_observation_expectations.sql`
- `models/marts/dimensions/properties/dim_staff_observation_expectations.yml`

**Spec grain:** One row per staff member x observation type term. Scaffolded by
crossing active teaching staff from roster history with PM/walkthrough/O3 term
windows.

**Key:** `staff_observation_expectation_key` =
`generate_surrogate_key(["employee_number", "type", "code", "name", "start_date", "region", "school_id"])`.

**FKs:**

- `staff_key` → `dim_staff`
- `term_key` → `dim_terms`

**Upstream:**

- `int_people__staff_roster_history` (active teachers during term overlap)
- `stg_google_sheets__reporting__terms` (PM/walkthrough term definitions)

Staff are filtered to primary_indicator = TRUE, assignment_status = 'Active',
and job_title containing 'Teacher' or 'Learning'. Terms are filtered to types
`PMS`, `PMC`, `TR`, `WT`, `O3`.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 6: `fct_staff_observations`

**Files:**

- `models/marts/facts/fct_staff_observations.sql`
- `models/marts/facts/properties/fct_staff_observations.yml`

**Spec grain:** One row per observation event. Combines SchoolMint Grow live
observations (2024+) with historical walkthrough data (2023).

**Key:** `staff_observation_key` = `generate_surrogate_key(["observation_id"])`.

**FKs:**

- `teacher_staff_key` → `dim_staff` (observed teacher)
- `observer_staff_key` → `dim_staff` (role-playing, observer)
- `location_key` → `dim_locations`
- `term_key` → `dim_terms` (joined by observation_type_abbreviation and
  observed_at date; null when observation falls outside any reporting term
  window)

**Upstream:**

- `int_performance_management__observations` (unified observation source)
- `int_schoolmint_grow__observations` (for school_name → location join)
- `int_people__location_crosswalk` (location_name → location_clean_name)
- `stg_google_sheets__reporting__terms` (term context)

Row with `rn = 1` (ordered by term_name asc nulls last) is kept to deduplicate
when an observation overlaps multiple terms.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 7: `fct_staff_observation_scores`

**Files:**

- `models/marts/facts/fct_staff_observation_scores.sql`
- `models/marts/facts/properties/fct_staff_observation_scores.yml`

**Spec grain:** One row per measurement item per observation.

**Key:** `staff_observation_score_key` =
`generate_surrogate_key(["observation_id", "measurement_id"])`.

**FKs:**

- `staff_observation_key` → `fct_staff_observations`
- `staff_observation_rubric_measurement_key` →
  `dim_staff_observation_rubric_measurements`

**Upstream:** `stg_schoolmint_grow__observations` (unnests `observation_scores`
array). Scoped to published observations present in `fct_staff_observations`.
HTML is stripped from textbox content via regex.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 8: `fct_staff_observation_microgoals`

**Files:**

- `models/marts/facts/fct_staff_observation_microgoals.sql`
- `models/marts/facts/properties/fct_staff_observation_microgoals.yml`

**Spec grain:** One row per teacher x goal assignment x tag.

**Key:** `staff_observation_microgoal_key` =
`generate_surrogate_key(["gu.internal_id_int", "a.assignment_id", "m.tag_id"])`.

**FKs:**

- `teacher_staff_key` → `dim_staff` (teacher receiving microgoal)
- `creator_staff_key` → `dim_staff` (role-playing, creator; nullable when
  creator cannot be matched to staff roster)
- `staff_observation_microgoal_type_key` →
  `dim_staff_observation_microgoal_types`

**Upstream:**

- `stg_schoolmint_grow__assignments` (assignment events)
- `stg_schoolmint_grow__users` (user → employee_number)
- `int_schoolmint_grow__assignments__tags` (assignment → tag pairs)
- `int_schoolmint_grow__microgoals` (tag taxonomy)
- `int_people__staff_roster` (creator name → employee_number)

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

## Verification checklist

- [x] `dim_staff_observation_rubric_measurements.staff_observation_rubric_key`
      has a relationships test back to `dim_staff_observation_rubrics`
- [x] `fct_staff_observation_scores.staff_observation_key` has a relationships
      test back to `fct_staff_observations`
- [x] `fct_staff_observation_microgoals.staff_observation_microgoal_type_key`
      has a relationships test back to `dim_staff_observation_microgoal_types`
- [x] `dim_staff_observation_expectations.staff_key` has a relationships test
      back to `dim_staff`
- [x] All uniqueness tests pass on primary keys
