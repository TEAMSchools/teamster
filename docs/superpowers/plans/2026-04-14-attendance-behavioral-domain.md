# Attendance & Behavioral Domain Implementation Plan

**Goal:** Build the attendance and behavioral domain — one dimension for
intervention type reference data, three attendance fact tables (daily, streaks,
interventions), two behavioral fact tables (incidents, consequences), and one
family communications fact table.

**Architecture:** `fct_student_attendance_daily` is the primary attendance grain
(one row per student x date). `fct_student_attendance_streaks` captures
consecutive-day streak events. `fct_student_attendance_interventions` tracks
chronic-absence communication completion against
`dim_student_attendance_intervention_types` thresholds. The behavioral cluster
follows an incident → consequence hierarchy (FK from consequences to incidents).
`fct_family_communications` covers all DeansList comm log entries.

**Tech Stack:** dbt (BigQuery dialect), `dbt_utils.generate_surrogate_key()`,
`union_dataset_join_clause()` macro (union model joins),
`extract_code_location()` macro.

**Spec reference:**
`docs/superpowers/specs/2026-03-27-star-schema-data-mart-design.md` — Attendance
and Behavioral Domain sections.

**Dependencies:** Plan 1 (Conformed Dimensions), Plan 2 (Student Domain for
dim_student_enrollments).

---

## Prerequisites

- Working directory:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-star-schema-data-mart/`
- All file paths relative to `src/dbt/kipptaf/`

## Task Overview

| Task | Model                                       | Type      | Dependencies |
| ---- | ------------------------------------------- | --------- | ------------ |
| 1    | `dim_student_attendance_intervention_types` | dimension | none         |
| 2    | `fct_student_attendance_daily`              | fact      | Task 1       |
| 3    | `fct_student_attendance_streaks`            | fact      | none         |
| 4    | `fct_student_attendance_interventions`      | fact      | Task 1       |
| 5    | `fct_behavioral_incidents`                  | fact      | none         |
| 6    | `fct_behavioral_consequences`               | fact      | Task 5       |
| 7    | `fct_family_communications`                 | fact      | none         |

---

### Task 1: `dim_student_attendance_intervention_types`

**Files:**

- `models/marts/dimensions/dim_student_attendance_intervention_types.sql`
- `models/marts/dimensions/properties/dim_student_attendance_intervention_types.yml`

**Spec grain:** One row per region x intervention threshold combination.
Hardcoded from business rules. Miami uses thresholds 3, 5, 8, 10, 15+; Newark
and Camden use 4, 8, 12, 16, 20, 30, 40.

**Key:** `intervention_type_key` =
`generate_surrogate_key(["region", "commlog_reason"])`.

**Upstream:** None — values are scaffolded from `UNNEST` literals.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 2: `fct_student_attendance_daily`

**Files:**

- `models/marts/facts/fct_student_attendance_daily.sql`
- `models/marts/facts/properties/fct_student_attendance_daily.yml`

**Spec grain:** One row per student x calendar date with attendance recorded.

**Key:** `student_attendance_daily_key` =
`generate_surrogate_key(["student_number", "calendardate"])`.

**FKs:**

- `student_enrollment_key` → `dim_student_enrollments`
- `date_key` → `dim_dates`
- `location_key` → `dim_locations` (also used with `date_key` to join
  `dim_school_calendars` without creating a diamond path)

**Upstream:**

- `int_powerschool__ps_adaadm_daily_ctod` (attendance records)
- `base_powerschool__student_enrollments` (enrollment context for FK)
- `int_people__location_crosswalk` (schoolid → location_clean_name)

Both `ada` and `enr` are union models; `union_dataset_join_clause()` is used in
the enrollment join. `extract_code_location()` aligns the location join across
union sources.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 3: `fct_student_attendance_streaks`

**Files:**

- `models/marts/facts/fct_student_attendance_streaks.sql`
- `models/marts/facts/properties/fct_student_attendance_streaks.yml`

**Spec grain:** One row per student x consecutive attendance streak (gaps-and-
islands result per att_code).

**Key:** `student_attendance_streak_key` = `streak_id` (natural key from
upstream intermediate model).

**FKs:**

- `student_enrollment_key` → `dim_student_enrollments`
- `streak_start_date_key` → `dim_dates` (role-playing)
- `streak_end_date_key` → `dim_dates` (role-playing)

**Upstream:**

- `int_powerschool__attendance_streak` (streak computation)
- `base_powerschool__student_enrollments` (student_number + entrydate for FK)

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 4: `fct_student_attendance_interventions`

**Files:**

- `models/marts/facts/fct_student_attendance_interventions.sql`
- `models/marts/facts/properties/fct_student_attendance_interventions.yml`

**Spec grain:** One row per student x intervention type x academic year.

**Key:** `student_attendance_intervention_key` =
`generate_surrogate_key(["student_number", "academic_year", "commlog_reason"])`.

**FKs:**

- `student_enrollment_key` → `dim_student_enrollments`
- `intervention_type_key` → `dim_student_attendance_intervention_types` (derived
  from region and commlog_reason)
- `date_key` → `dim_dates` (null when intervention is missing/not yet completed)

**Upstream:**

- `int_students__attendance_interventions` (DeansList comm log + absence counts)
- `base_powerschool__student_enrollments` (enrollment context, rn_year = 1)

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 5: `fct_behavioral_incidents`

**Files:**

- `models/marts/facts/fct_behavioral_incidents.sql`
- `models/marts/facts/properties/fct_behavioral_incidents.yml`

**Spec grain:** One row per student x incident from DeansList.

**Key:** `behavioral_incident_key` =
`generate_surrogate_key(["incident_id", "_dbt_source_relation"])`.

**FKs:**

- `student_enrollment_key` → `dim_student_enrollments`
- `date_key` → `dim_dates`

**Note:** Referring staff are identified by name only — DeansList does not
expose employee_number, so no FK to `dim_staff`.

**Upstream:**

- `int_deanslist__incidents` (incident records)
- `base_powerschool__student_enrollments` (most recent enrollment per student x
  academic_year x source, rn = 1)
- `int_people__location_crosswalk` (schoolid → location for supplemental
  context)

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 6: `fct_behavioral_consequences`

**Files:**

- `models/marts/facts/fct_behavioral_consequences.sql`
- `models/marts/facts/properties/fct_behavioral_consequences.yml`

**Spec grain:** One row per student x incident x consequence (penalty).

**Key:** `behavioral_consequence_key` =
`generate_surrogate_key(["incident_id", "incident_penalty_id", "_dbt_source_relation"])`.

**FKs:**

- `behavioral_incident_key` → `fct_behavioral_incidents`
- `start_date_key` → `dim_dates` (role-playing, nullable)
- `end_date_key` → `dim_dates` (role-playing, nullable)

**Note:** Student, location, and region context is traversed through the parent
incident record — not repeated here.

**Upstream:**

- `int_deanslist__incidents__penalties` (consequence records)
- `base_powerschool__student_enrollments` (enrollment join, rn = 1)

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 7: `fct_family_communications`

**Files:**

- `models/marts/facts/fct_family_communications.sql`
- `models/marts/facts/properties/fct_family_communications.yml`

**Spec grain:** One row per communication event from DeansList comm log.
General-purpose, covering all communication types (attendance, truancy,
general).

**Key:** `family_communication_key` =
`generate_surrogate_key(["record_id", "_dbt_source_relation"])`.

**FKs:**

- `student_enrollment_key` → `dim_student_enrollments`
- `date_key` → `dim_dates`

**Upstream:**

- `int_deanslist__comm_log` (communication records)
- `base_powerschool__student_enrollments` (most recent enrollment, rn = 1)

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

## Verification checklist

- [x] `fct_student_attendance_daily.location_key` matches
      `dim_school_calendars.location_key` (same surrogate derivation from
      `location_clean_name`)
- [x] `fct_behavioral_consequences.behavioral_incident_key` matches
      `fct_behavioral_incidents.behavioral_incident_key` surrogate derivation
- [x] `union_dataset_join_clause()` used wherever union models are joined
- [x] All uniqueness tests pass on primary keys
- [x] `fct_student_attendance_interventions.intervention_type_key` derivation
      matches `dim_student_attendance_intervention_types`
