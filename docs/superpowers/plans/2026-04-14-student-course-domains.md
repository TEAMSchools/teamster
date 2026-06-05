# Student + Course Domains Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the student and course domain dimensions and bridges that enable
enrollment-level, section-level, and contact-level analysis.

**Architecture:** Student dimensions form a chain: `dim_students` →
`dim_student_enrollments` → `dim_student_section_enrollments`. Course
dimensions: `dim_courses` → `dim_course_sections`. Bridges resolve N:M
relationships: `bridge_student_contacts`, `bridge_course_section_teachers`,
`bridge_course_section_terms`. All live in `models/marts/dimensions/` or
`models/marts/bridges/`.

**Tech Stack:** dbt (BigQuery dialect), `dbt_utils.generate_surrogate_key()`,
`uv run dbt build`.

**Spec reference:**
`docs/superpowers/specs/2026-03-27-star-schema-data-mart-design.md` — Student
Domain, Course Domain sections.

**Dependency:** Plan 1 (Conformed Dimensions) must be complete. `dim_staff`
(Plan 3) is needed for `bridge_course_section_teachers` — that bridge is
deferred to Plan 3.

---

## Prerequisites

- Working directory:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-star-schema-data-mart/`
- All commands use `uv run` prefix
- All file paths relative to `src/dbt/kipptaf/`
- Plan 1 conformed dimensions already built

## Task Overview

| Task | Model                             | Action | Dependencies |
| ---- | --------------------------------- | ------ | ------------ |
| 1    | `dim_students`                    | revise | none         |
| 2    | `dim_student_enrollments`         | create | Task 1       |
| 3    | `dim_student_contact_persons`     | create | none         |
| 4    | `bridge_student_contacts`         | create | Tasks 1, 3   |
| 5    | `dim_courses`                     | create | none         |
| 6    | `dim_course_sections`             | create | Task 5       |
| 7    | `dim_student_section_enrollments` | create | Tasks 2, 6   |
| 8    | `bridge_course_section_terms`     | create | Task 6       |

`bridge_course_section_teachers` is deferred to Plan 3 (requires `dim_staff`).

---

### Task 1: `dim_students`

Revise existing prototype. The current `dim_students` mixes person + enrollment
data. The new version is **person-only** (Type 1, one row per student). Split
enrollment data to `dim_student_enrollments` (Task 2).

**Files:**

- Create: `models/marts/dimensions/dim_students.sql`
- Create: `models/marts/dimensions/properties/dim_students.yml`
- Delete: `models/marts/dim_students.sql` +
  `models/marts/properties/dim_students.yml`

**Spec grain:** One row per student.

**Spec columns:** local_student_identifier (student_number),
state_student_identifier, name, birth_date, gender, race/ethnicity, is_gifted,
is_ell, has_iep (from edplan), lunch_status (from Titan).

**Upstream:** `int_extracts__student_enrollments` — deduplicate to one row per
student using
`ROW_NUMBER() OVER (PARTITION BY student_number ORDER BY academic_year DESC, entrydate DESC) = 1`.
Person-level columns are stable across enrollments; take the most recent.

**Key:** `student_key` = `generate_surrogate_key(["student_number"])`.

- [ ] **Step 1: Write YAML contract** with `student_key` (unique + not_null),
      person-level columns only, descriptions on all. Read
      `models/marts/properties/dim_students.yml` for reference, but the new
      version strips enrollment columns.

- [ ] **Step 2: Write SQL model** — CTE deduplicating
      `int_extracts__student_enrollments` to one row per student_number,
      selecting only person-level columns.

- [ ] **Step 3: Delete old prototype, build and test**

```bash
git rm src/dbt/kipptaf/models/marts/dim_students.sql src/dbt/kipptaf/models/marts/properties/dim_students.yml
uv run dbt build -s dim_students --project-dir src/dbt/kipptaf
```

- [ ] **Step 4: Commit**

---

### Task 2: `dim_student_enrollments`

New model. One row per student x school x year. Each enrollment is a distinct
record with entry/exit dates (Type 1, not Type 2 — these are not versions of the
same enrollment).

**Files:**

- Create: `models/marts/dimensions/dim_student_enrollments.sql`
- Create: `models/marts/dimensions/properties/dim_student_enrollments.yml`

**Spec grain:** One row per student x school x year.

**Spec columns:** grade_level, graduation_year, school_level, enroll_status,
is_retained_year. FKs: student_key → dim_students, location_key → dim_locations,
entry_date_key → dim_dates, exit_date_key → dim_dates (nullable).

**Upstream:** `base_powerschool__student_enrollments` (already at this grain).
Join to `int_people__location_crosswalk` for location_key generation (same
surrogate pattern as `dim_locations`).

**Key:** `student_enrollment_key` =
`generate_surrogate_key(["student_number", "_dbt_source_relation", "academic_year", "entrydate"])`
— matches the existing uniqueness test on `int_extracts__student_enrollments`.

- [ ] **Step 1: Write YAML contract** with `student_enrollment_key` (unique +
      not_null), FK columns, enrollment attributes, descriptions.

- [ ] **Step 2: Write SQL model** — select from
      `base_powerschool__student_enrollments`, generate surrogate keys for
      student_key and location_key consistent with dim_students and
      dim_locations. Use `{{ union_dataset_join_clause() }}` or
      `{{ extract_code_location() }}` for cross-region join to location
      crosswalk.

- [ ] **Step 3: Build and test**

- [ ] **Step 4: Commit**

---

### Task 3: `dim_student_contact_persons`

New model. One row per unique contact person. Deduped across students — one
parent who appears on multiple students' records collapses into a single row.

**Files:**

- Create: `models/marts/dimensions/dim_student_contact_persons.sql`
- Create: `models/marts/dimensions/properties/dim_student_contact_persons.yml`

**Spec grain:** One row per unique contact person.

**Spec columns:** contact_name, phone, email, address.

**Upstream:** `base_powerschool__student_contact_union` — this model unpivots
the flattened contact columns from PowerSchool student records. Explore it to
determine the exact column structure and deduplication key.

**Key:** `student_contact_person_key` — determine the natural key from the
upstream (likely a person identifier or hash of contact attributes).

- [ ] **Step 1: Explore upstream** — read
      `base_powerschool__student_contact_union` SQL and YAML to understand
      columns and grain.

- [ ] **Step 2: Write YAML contract**

- [ ] **Step 3: Write SQL model**

- [ ] **Step 4: Build and test**

- [ ] **Step 5: Commit**

---

### Task 4: `bridge_student_contacts`

New model. Resolves the N:M between students and contact persons. One row per
student x contact person pairing.

**Files:**

- Create: `models/marts/bridges/bridge_student_contacts.sql`
- Create: `models/marts/bridges/properties/bridge_student_contacts.yml`

**Spec grain:** One row per student x contact person.

**Spec columns:** relationship, is_emergency, is_primary, contact_priority. FK
to dim_students (student_key), dim_student_contact_persons
(student_contact_person_key).

**Upstream:** Same as Task 3 — `base_powerschool__student_contact_union` likely
has student-contact pair rows with relationship metadata.

- [ ] **Step 1: Write YAML contract**

- [ ] **Step 2: Write SQL model**

- [ ] **Step 3: Build and test**

- [ ] **Step 4: Commit**

---

### Task 5: `dim_courses`

New model. Course catalog dimension. One row per course.

**Files:**

- Create: `models/marts/dimensions/dim_courses.sql`
- Create: `models/marts/dimensions/properties/dim_courses.yml`

**Spec grain:** One row per course in catalog.

**Spec columns:** course_number, course_name, discipline (credittype),
credit_hours.

**Upstream:** `stg_powerschool__courses` (kipptaf union model). Explore the
kipptaf staging model for columns. The source-system `stg_powerschool__courses`
has course_number, course_name, credittype, credit_hours.

**Key:** `course_key` = `generate_surrogate_key(["course_number"])` — course
numbers are unique within the catalog.

- [ ] **Step 1: Write YAML contract**

- [ ] **Step 2: Write SQL model** — select distinct courses from the staging
      model. Map `credittype` → `discipline` (generic naming).

- [ ] **Step 3: Build and test**

- [ ] **Step 4: Commit**

---

### Task 6: `dim_course_sections`

New model. One row per section. FK to dim_courses and dim_locations.

**Files:**

- Create: `models/marts/dimensions/dim_course_sections.sql`
- Create: `models/marts/dimensions/properties/dim_course_sections.yml`

**Spec grain:** One row per section.

**Spec columns:** section_number, period, room. FK to dim_courses,
dim_locations.

**Upstream:** `base_powerschool__sections` (powerschool base model) — already at
section grain. Contains sections*\*, courses*\_, terms\_\_, school_name columns.
Accessed via kipptaf union: `stg_powerschool__sections` → kipptaf or directly
via `base_powerschool__course_enrollments` which joins sections.

**Key:** `course_section_key` — determine from upstream (likely section_id or
dcid + source_relation).

- [ ] **Step 1: Explore upstream** — find the kipptaf-level model that provides
      section data at the right grain with school context.

- [ ] **Step 2: Write YAML contract**

- [ ] **Step 3: Write SQL model**

- [ ] **Step 4: Build and test**

- [ ] **Step 5: Commit**

---

### Task 7: `dim_student_section_enrollments`

New model. One row per student x section. Roster membership.

**Files:**

- Create: `models/marts/dimensions/dim_student_section_enrollments.sql`
- Create:
  `models/marts/dimensions/properties/dim_student_section_enrollments.yml`

**Spec grain:** One row per student x section.

**Spec FKs:** dim_student_enrollments, dim_course_sections, dim_terms.

**Upstream:** `base_powerschool__course_enrollments` — has cc*\*
(student-section enrollment) and sections*\_/courses\_\_ columns. Grain is
student x section.

**Key:** `student_section_enrollment_key` — generate from student_number +
section identifier.

- [ ] **Step 1: Write YAML contract**

- [ ] **Step 2: Write SQL model** — generate FKs (student_enrollment_key,
      course_section_key, term_key) consistent with their parent dims.

- [ ] **Step 3: Build and test**

- [ ] **Step 4: Commit**

---

### Task 8: `bridge_course_section_terms`

New model. Maps each section to every term it runs in. A year-long section at a
quarterly school produces 4 bridge rows.

**Files:**

- Create: `models/marts/bridges/bridge_course_section_terms.sql`
- Create: `models/marts/bridges/properties/bridge_course_section_terms.yml`

**Spec grain:** One row per section x term.

**Spec FKs:** dim_course_sections, dim_terms.

**Upstream:** PowerSchool `termsections` or derive from section term data in
`base_powerschool__sections` (which carries terms\_\* columns).

- [ ] **Step 1: Explore upstream** — find the PowerSchool model that maps
      sections to terms (look for `termsections` staging or term data on
      sections).

- [ ] **Step 2: Write YAML contract**

- [ ] **Step 3: Write SQL model**

- [ ] **Step 4: Build and test**

- [ ] **Step 5: Commit**

---

## Verification checklist

After all tasks complete:

- [ ] 6 new `.sql` files in `models/marts/dimensions/`
- [ ] 2 new `.sql` files in `models/marts/bridges/`
- [ ] No old `dim_students` prototype in `models/marts/` root
- [ ] `uv run dbt build -s dim_students dim_student_enrollments dim_student_contact_persons bridge_student_contacts dim_courses dim_course_sections dim_student_section_enrollments bridge_course_section_terms`
      passes all tests
- [ ] FK surrogate keys are consistent across models (same inputs → same hash)
