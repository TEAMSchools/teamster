# Remaining Domains Implementation Plan

**Goal:** Build the remaining mart domains — college persistence (dim_colleges,
dim_college_enrollments), recruiting (dim_job_postings, dim_job_candidates,
dim_staffing_positions, fct_job_candidate_applications), and IT support
(fct_support_tickets).

**Architecture:** College persistence uses NSC data enriched via a
Salesforce/kippadb crosswalk. `dim_college_enrollments` is a tenure-collapsed
dimension (one row per student x college), not a fact table. The recruiting
cluster is isolated to SmartRecruiters — no FK to `dim_staff` or
`dim_staffing_positions`. `dim_staffing_positions` is a Type 2 SCD sourced from
a dbt snapshot of the AppSheet seat tracker. `fct_support_tickets` joins Zendesk
data to the staff roster via email match.

**Tech Stack:** dbt (BigQuery dialect), `dbt_utils.generate_surrogate_key()`,
`dbt_utils.deduplicate()`, NSC/kippadb/SmartRecruiters/Zendesk sources.

**Spec reference:**
`docs/superpowers/specs/2026-03-27-star-schema-data-mart-design.md` — remaining
domain sections.

**Dependencies:** Plan 1 (Conformed Dimensions), Plan 2 (Student Domain for
`dim_students`), Plan 3 (Staff Domain for `dim_staff` and `dim_locations`).

---

## Prerequisites

- Working directory:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-star-schema-data-mart/`
- All file paths relative to `src/dbt/kipptaf/`

## Task Overview

| Task | Model                            | Type | Dependencies    |
| ---- | -------------------------------- | ---- | --------------- |
| 1    | `dim_colleges`                   | dim  | none            |
| 2    | `dim_college_enrollments`        | dim  | Task 1          |
| 3    | `dim_job_postings`               | dim  | none            |
| 4    | `dim_job_candidates`             | dim  | none            |
| 5    | `fct_job_candidate_applications` | fact | Tasks 3, 4      |
| 6    | `dim_staffing_positions`         | dim  | Plan 3 complete |
| 7    | `fct_support_tickets`            | fact | Plan 3 complete |

---

### Task 1: `dim_colleges`

**Files:**

- `models/marts/dimensions/dim_colleges.sql`
- `models/marts/dimensions/properties/dim_colleges.yml`

**Spec grain:** One row per unique college identified by `college_code_branch`
(NSC college code including branch suffix).

**Key:** `college_key` = `generate_surrogate_key(["college_code_branch"])`.

**Upstream:**

- `stg_nsc__student_tracker` (college name, state, two_year_four_year; filtered
  to `record_found_y_n = 'Y'`)
- `stg_google_sheets__kippadb__nsc_crosswalk` (NCES ID, meets_full_need,
  is_strong_oos_option; `rn_college_code_nsc = 1`)
- `stg_kippadb__account` (selectivity, account_type, is_hbcu)

`dbt_utils.deduplicate()` on `college_code_branch`, ordered by
`college_name desc`.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 2: `dim_college_enrollments`

**Files:**

- `models/marts/dimensions/dim_college_enrollments.sql`
- `models/marts/dimensions/properties/dim_college_enrollments.yml`

**Spec grain:** One row per student x college combination — tenure-collapsed
across all NSC enrollment records. Not a fact table; models the student's full
relationship with a college as a single descriptive record.

**Key:** `college_enrollment_key` =
`generate_surrogate_key(["student_number", "college_code_branch"])`.

**FKs:**

- `student_key` → `dim_students`
- `college_key` → `dim_colleges`
- `start_date_key` → `dim_dates` (role-playing, earliest enrollment_begin)
- `end_date_key` → `dim_dates` (role-playing, latest enrollment_end)

**Upstream:**

- `stg_nsc__student_tracker` (all enrollment rows per contact x college)
- `int_kippadb__roster` (contact_id → student_number crosswalk)

The CTE `nsc_tenure` collapses rows to one per contact x college using
`MIN(enrollment_begin)`, `MAX(enrollment_end)`, and conditional aggregation to
derive latest enrollment status, degree, major, and class_level from the
most-recent enrollment_end record.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 3: `dim_job_postings`

**Files:**

- `models/marts/dimensions/dim_job_postings.sql`
- `models/marts/dimensions/properties/dim_job_postings.yml`

**Spec grain:** One row per unique job posting identified by the combination of
`job_title`, `department_internal`, and `job_city`.

**Key:** `job_posting_key` =
`generate_surrogate_key(["job_title", "department_internal", "job_city"])`.

**Upstream:** `stg_smartrecruiters__applications`. `dbt_utils.deduplicate()` on
the grain, ordered by `new_date desc` (most recently opened posting).

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 4: `dim_job_candidates`

**Files:**

- `models/marts/dimensions/dim_job_candidates.sql`
- `models/marts/dimensions/properties/dim_job_candidates.yml`

**Spec grain:** One row per unique candidate.

**Key:** `job_candidate_key` = `generate_surrogate_key(["candidate_id"])`.

**Upstream:** `stg_smartrecruiters__applications`. `dbt_utils.deduplicate()` on
`candidate_id`, ordered by `new_date desc`.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 5: `fct_job_candidate_applications`

**Files:**

- `models/marts/facts/fct_job_candidate_applications.sql`
- `models/marts/facts/properties/fct_job_candidate_applications.yml`

**Spec grain:** One row per application.

**Key:** `job_candidate_application_key` =
`generate_surrogate_key(["application_id"])`.

**FKs:**

- `job_candidate_key` → `dim_job_candidates`
- `job_posting_key` → `dim_job_postings`
- `created_date_key` → `dim_dates`

**Note:** No FK to `dim_staff` or `dim_staffing_positions` — SmartRecruiters is
an isolated domain with no reliable staff_key join path.

**Upstream:** `stg_smartrecruiters__applications` (pass-through — one row per
application with all status, stage, date, time-in-stage, and scoring columns).

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 6: `dim_staffing_positions`

**Files:**

- `models/marts/dimensions/dim_staffing_positions.sql`
- `models/marts/dimensions/properties/dim_staffing_positions.yml`

**Spec grain:** One row per budgeted position per snapshot version (Type 2 SCD).
Multiple versions of the same `staffing_model_id` exist when attributes change.

**Key:** `staffing_position_key` = `generate_surrogate_key(["dbt_scd_id"])`
(snapshot row identifier).

**FKs:**

- `location_key` → `dim_locations` (derived from `adp_location`)
- `teammate_staff_key` → `dim_staff` (role-playing, assigned staff member;
  nullable for open positions)
- `recruiter_staff_key` → `dim_staff` (role-playing; nullable)

**SCD columns:** `effective_date_start` (dbt_valid_from cast to date),
`effective_date_end` (dbt_valid_to cast to date; NULL for current version).

**Upstream:** `snapshot_seat_tracker__seats` (dbt snapshot of AppSheet seat
tracker).

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 7: `fct_support_tickets`

**Files:**

- `models/marts/facts/fct_support_tickets.sql`
- `models/marts/facts/properties/fct_support_tickets.yml`

**Spec grain:** One row per staff-submitted Zendesk ticket. Scoped to tickets
whose submitter email matches an active KIPP staff member (inner join to staff
roster).

**Key:** `support_ticket_key` = `generate_surrogate_key(["t.id"])`.

**FKs:**

- `submitter_staff_key` → `dim_staff` (required; inner join)
- `assignee_staff_key` → `dim_staff` (role-playing; nullable — unassigned
  tickets)
- `original_assignee_staff_key` → `dim_staff` (role-playing; nullable)
- `location_key` → `dim_locations` (derived from Zendesk custom Location field)
- `created_date_key` → `dim_dates`
- `solved_date_key` → `dim_dates` (role-playing; nullable for open tickets)

**Upstream:**

- `source("zendesk", "tickets")` (ticket records; deleted tickets excluded)
- `stg_zendesk__users` (email → staff email match)
- `int_people__staff_roster` (email → employee_number for staff keys)
- `stg_zendesk__ticket_audits__events` (original assignee from Create event)
- `int_zendesk__tickets__custom_fields_pivot` (category, tech_tier, location)
- `stg_zendesk__ticket_metrics` (reply count, business minutes to solve)

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

## Verification checklist

- [x] `dim_college_enrollments` grain is one row per student x college
      (tenure-collapsed, not per NSC enrollment row)
- [x] `dim_staffing_positions` has `effective_date_start/end` from dbt snapshot
      SCD columns
- [x] `fct_job_candidate_applications` has no FK to `dim_staff` or
      `dim_staffing_positions` (SmartRecruiters isolation)
- [x] `fct_support_tickets` submitter is inner-joined (excludes non-staff
      tickets)
- [x] All uniqueness tests pass on primary keys
