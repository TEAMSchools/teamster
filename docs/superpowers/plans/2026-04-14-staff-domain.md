# Staff Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the staff/HR domain dimensions and facts covering worker
identity, work assignments, SCD Type 2 versioned attributes, compensation,
attrition, benefits, memberships, and the course section teacher bridge deferred
from Plan 2.

**Architecture:** Two-level hierarchy: `dim_staff` (person) →
`dim_staff_work_assignments` (assignment) → Type 2 child dims/facts for
high-churn attributes. Person-level facts (`fct_staff_attrition`,
`fct_staff_benefits_enrollments`, `fct_staff_membership_enrollments`) FK to
`dim_staff` directly. Assignment-level facts FK to `dim_staff_work_assignments`.

**Tech Stack:** dbt (BigQuery dialect), `dbt_utils.generate_surrogate_key()`,
`uv run dbt build`.

**Spec reference:**
`docs/superpowers/specs/2026-03-27-star-schema-data-mart-design.md` — Staff
Domain section.

**Dependencies:** Plan 1 (Conformed Dimensions), Plan 2 (Student + Course for
bridge_course_section_teachers).

---

## Prerequisites

- Working directory:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-star-schema-data-mart/`
- All commands: `uv run dbt build --project-dir src/dbt/kipptaf`
- All file paths relative to `src/dbt/kipptaf/`

## Task Overview

### Tier 1 — Type 1 models (straightforward)

| Task | Model                              | Type   | Dependencies |
| ---- | ---------------------------------- | ------ | ------------ |
| 1    | `dim_staff`                        | Type 1 | none         |
| 2    | `dim_staff_work_assignments`       | Type 1 | Task 1       |
| 3    | `fct_staff_attrition`              | Type 1 | Task 1       |
| 4    | `fct_staff_benefits_enrollments`   | Type 1 | Task 1       |
| 5    | `fct_staff_membership_enrollments` | Type 1 | Task 1       |
| 6    | `bridge_course_section_teachers`   | bridge | Task 1       |

### Tier 2 — Type 2 SCD models (complex)

| Task | Model                                         | Type                | Dependencies |
| ---- | --------------------------------------------- | ------------------- | ------------ |
| 7    | `dim_staff_status`                            | Type 2 (derived)    | Task 1       |
| 8    | `dim_work_assignment_status`                  | Type 2 (src-native) | Task 2       |
| 9    | `dim_work_assignment_jobs`                    | Type 2 (derived)    | Task 2       |
| 10   | `dim_work_assignment_types`                   | Type 2 (derived)    | Task 2       |
| 11   | `dim_work_assignment_locations`               | Type 2 (derived)    | Task 2       |
| 12   | `dim_work_assignment_organizational_units`    | Type 2 (derived)    | Task 2       |
| 13   | `dim_work_assignment_reporting_relationships` | Type 2 (derived)    | Task 2       |
| 14   | `fct_work_assignment_compensation`            | Type 2 (src-native) | Task 2       |
| 15   | `fct_work_assignment_additional_earnings`     | Type 2 (src-native) | Task 2       |

---

### Task 1: `dim_staff`

Revise existing prototype. The new version is **Type 1** (one row per person,
current state). The existing prototype is Type 2 — simplify it.

**Files:**

- Create: `models/marts/dimensions/dim_staff.sql`
- Create: `models/marts/dimensions/properties/dim_staff.yml`
- Delete: `models/marts/dim_staff.sql` + `models/marts/properties/dim_staff.yml`

**Spec grain:** One row per person.

**Key:** `staff_key` = `generate_surrogate_key(["employee_number"])`.
`employee_number` is a KIPP-generated identifier (via
`stg_people__employee_numbers`), not an ADP-native field.

**Spec columns from ADP `Worker.person`:** names, demographics (birth_date,
race, ethnicity, gender), addresses, communication (phone, email). Also
`Worker.workerDates` (original hire, rehire), `Worker.customFieldGroup`, and
LDAP fields (SAM account, email).

**Upstream:** `int_people__staff_roster_history` — deduplicate to one row per
employee_number using most recent record. OR `int_people__staff_roster` which is
already current-state. Prefer the roster (simpler).

- [ ] **Step 1: Explore upstreams** — read `int_people__staff_roster` SQL/YAML
      to confirm it's one-row-per-employee current state.

- [ ] **Step 2: Write YAML contract** — person-level attributes only, generic
      naming.

- [ ] **Step 3: Write SQL model** — select from `int_people__staff_roster`,
      rename to generic names.

- [ ] **Step 4: Delete old prototype, build and test**

- [ ] **Step 5: Commit**

---

### Task 2: `dim_staff_work_assignments`

New model. One row per work assignment (Type 1 — current state only).

**Files:**

- Create: `models/marts/dimensions/dim_staff_work_assignments.sql`
- Create: `models/marts/dimensions/properties/dim_staff_work_assignments.yml`

**Spec grain:** One row per assignment.

**Key:** `work_assignment_key` — surrogate from assignment identifier.

**Spec columns:** ADP `WorkAssignment` scalars + static structs — positionID,
flags (primary, management, voluntary), FTE, payroll fields, dates (hire, start,
seniority, termination), workerTimeProfile, wageLawCoverage, payCycleCode,
standardHours. FK: `staff_key` → dim_staff.

**Upstream:** `int_adp_workforce_now__workers__work_assignments` — has all work
assignment fields. Filter to current records.

- [ ] **Step 1: Explore upstream** — read the work assignments intermediate
      model to understand columns and how to identify current records.

- [ ] **Step 2: Write YAML contract**

- [ ] **Step 3: Write SQL model**

- [ ] **Step 4: Build and test**

- [ ] **Step 5: Commit**

---

### Task 3: `fct_staff_attrition`

Revise existing prototype. One row per employee x academic_year x
attrition_type.

**Files:**

- Create: `models/marts/facts/fct_staff_attrition.sql`
- Create: `models/marts/facts/properties/fct_staff_attrition.yml`
- Delete: `models/marts/fct_staff_attrition.sql` +
  `models/marts/properties/fct_staff_attrition.yml`

**Spec grain:** One row per employee x academic_year x attrition_type.

**Key:** `staff_attrition_key` — surrogate from employee_number +
academic_year + attrition_type.

**Spec columns:** staff_status_key (FK to dim_staff_status), academic_year,
attrition_type (foundation/nj_compliance/recruitment), attrition_cutoff_date,
is_attrition, termination_reason, termination_effective_date.

**Note:** FK to `dim_staff_status` depends on Task 7. For now, generate the FK
key but don't enforce referential integrity. The attrition logic itself should
match the existing prototype.

**Upstream:** existing `fct_staff_attrition` prototype +
`int_people__staff_roster_history`.

- [ ] **Step 1: Read existing prototype**
- [ ] **Step 2: Write YAML contract**
- [ ] **Step 3: Write SQL model**
- [ ] **Step 4: Delete old prototype, build and test**
- [ ] **Step 5: Commit**

---

### Task 4: `fct_staff_benefits_enrollments`

Revise existing prototype. One row per staff x benefit plan x enrollment period.

**Files:**

- Create: `models/marts/facts/fct_staff_benefits_enrollments.sql`
- Create: `models/marts/facts/properties/fct_staff_benefits_enrollments.yml`
- Delete: `models/marts/fct_staff_benefits_enrollments.sql` +
  `models/marts/properties/fct_staff_benefits_enrollments.yml`

**Spec grain:** One row per staff x benefit plan x enrollment period.

**FKs:** `staff_key` → dim_staff, `dim_dates` (enrollment_start_date,
enrollment_end_date as role-playing).

**Degenerate dimensions:** plan_type, plan_name, coverage_level.

**Upstream:** `stg_adp_workforce_now__pension_and_benefits_enrollments`.

- [ ] **Steps 1-5:** Same pattern as other tasks.

---

### Task 5: `fct_staff_membership_enrollments`

New model. One row per staff x program x enrollment period.

**Files:**

- Create: `models/marts/facts/fct_staff_membership_enrollments.sql`
- Create: `models/marts/facts/properties/fct_staff_membership_enrollments.yml`

**Spec grain:** One row per staff x program x enrollment period.

**FKs:** `staff_key` → dim_staff, `dim_dates` (enrollment_start_date,
enrollment_end_date as role-playing).

**Degenerate dimensions:** membership_code, membership_description,
category_code, category_description.

**Upstream:** `stg_adp_workforce_now__employee_memberships`.

- [ ] **Steps 1-5:** Same pattern.

---

### Task 6: `bridge_course_section_teachers`

Deferred from Plan 2. One row per section x teacher. Resolves N:M.

**Files:**

- Create: `models/marts/bridges/bridge_course_section_teachers.sql`
- Create: `models/marts/bridges/properties/bridge_course_section_teachers.yml`

**Spec grain:** One row per section x teacher.

**FKs:** `course_section_key` → dim_course_sections, `staff_key` → dim_staff.

**Columns:** teacher role (lead, co-teacher, etc.), effective dates per
assignment.

**Upstream:** PowerSchool `sectionteacher` staging model + teacher number
crosswalk to get employee_number for staff_key generation.

- [ ] **Steps 1-5:** Same pattern.

---

### Tasks 7-15: Type 2 SCD models

These are the most complex models in the mart. Each requires:

1. **Source-native** (Tasks 8, 14, 15): ADP provides `effectiveDate` — load rows
   directly on each new effective date observed.
2. **Derived** (Tasks 7, 9-13): construct effective dates from daily
   payload-hash diffs.

All Type 2 models produce: `effective_date_start`, `effective_date_end`,
`is_current_record` columns.

**Upstream for derived models:**
`int_adp_workforce_now__workers__work_assignments` has the full work assignment
data with nested arrays. The daily ADP API snapshots (external tables refreshed
daily) provide the temporal dimension for hash-based change detection.

These tasks require investigating how the existing daily snapshot mechanism
works and building the hash-diff logic. They may need new intermediate models.

- [ ] **Task 7:** `dim_staff_status` — worker-level status (Active/Terminated)
- [ ] **Task 8:** `dim_work_assignment_status` — assignment status + reason
- [ ] **Task 9:** `dim_work_assignment_jobs` — job title + job code
- [ ] **Task 10:** `dim_work_assignment_types` — worker type + benefits class
- [ ] **Task 11:** `dim_work_assignment_locations` — home work location
- [ ] **Task 12:** `dim_work_assignment_organizational_units` — org units
- [ ] **Task 13:** `dim_work_assignment_reporting_relationships` — reports-to
- [ ] **Task 14:** `fct_work_assignment_compensation` — base remuneration
- [ ] **Task 15:** `fct_work_assignment_additional_earnings` — supplemental pay

---

## Verification checklist

After Tier 1 tasks complete:

- [ ] `dim_staff` and `dim_staff_work_assignments` in `models/marts/dimensions/`
- [ ] `fct_staff_attrition`, `fct_staff_benefits_enrollments`,
      `fct_staff_membership_enrollments` in `models/marts/facts/`
- [ ] `bridge_course_section_teachers` in `models/marts/bridges/`
- [ ] All prototypes in `models/marts/` root cleaned up
- [ ] All tests pass

After Tier 2 tasks complete:

- [ ] All Type 2 dims in `models/marts/dimensions/` with
      `effective_date_start/end`, `is_current_record`
- [ ] All Type 2 facts in `models/marts/facts/`
- [ ] All tests pass
