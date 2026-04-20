# Cube Model YAML Design

**Date:** 2026-04-17 **Status:** Draft

## Overview

Define the YAML conventions, patterns, and reference implementations for the
Cube semantic layer model files that sit on top of the infrastructure
established in the
[Cube infrastructure spec](2026-04-15-cube-infrastructure-design.md). This spec
covers how the 67 dbt mart models from `models/marts/` map to cube files, how
SCD Type 2 tables are handled for point-in-time queries, and how the
detail/summary access split is enforced via views and access policies.

## Goals

- Clear conventions for when a dbt model becomes its own cube file vs gets
  inlined into a parent cube's SQL
- A reusable pattern for SCD2 period intersection that makes headcount-over-time
  and any other snapshot query correct at any point in time
- Two consumer-facing views per domain (detail and summary) with access policies
  that enforce the three-layer security model from the infrastructure spec
- One reference implementation per domain so engineers have a working template
  to follow for each domain's remaining models

## Non-goals

- Full field enumeration for all 67 models — implementation plan
- Pre-aggregations — follow-up spec
- Downstream integrations (Tableau, Superset, Streamlit) — follow-up spec
- `cube.js` configuration — covered in the infrastructure spec

## Repository Structure

```text
src/cube/model/
  cubes/
    conformed/
      dates.yml
      locations.yml
      regions.yml
      terms.yml
      school_calendars.yml
    students/
      students.yml              # dim_students — Type 1 wrapper + PII
      student_enrollments.yml   # SCD2 domain cube: headcount over time
    staff/
      staff.yml                 # dim_staff — Type 1 wrapper + PII
      staff_work_history.yml    # SCD2 domain cube: period intersection
      staff_compensation.yml
      staff_attrition.yml
      staff_benefits.yml
    attendance/
      attendance.yml
      attendance_interventions.yml
      attendance_streaks.yml
    behavioral/
      behavioral.yml
      family_communications.yml
    gradebook/
      grades_term.yml
      grades_gpa.yml
      grades_category.yml
      grades_assignments.yml
    assessment/
      assessment_scores.yml
      assessment_scores_student_scoped.yml
    observations/
      observations.yml
      observation_scores.yml
      observation_microgoals.yml
    surveys/
      surveys.yml
      survey_responses.yml
    college/
      college.yml
    talent/
      talent.yml
    staffing/
      staffing.yml
    support/
      support.yml
  views/
    students/
      students_detail.yml
      students_summary.yml
    staff/
      staff_detail.yml
      staff_summary.yml
    attendance/
      attendance_detail.yml
      attendance_summary.yml
    behavioral/
      behavioral_detail.yml
      behavioral_summary.yml
    gradebook/
      gradebook_detail.yml
      gradebook_summary.yml
    assessment/
      assessment_detail.yml
      assessment_summary.yml
    observations/
      observations_detail.yml
      observations_summary.yml
    surveys/
      surveys_detail.yml
      surveys_summary.yml
    college/
      college_detail.yml
      college_summary.yml
    talent/
      talent_detail.yml
      talent_summary.yml
    staffing/
      staffing_detail.yml
      staffing_summary.yml
    support/
      support_detail.yml
      support_summary.yml
```

Total cube files: ~35 (down from 67 dbt models). Views: 26 (2 per domain × 13
domains including students).

## Domain Breakdown

How the 67 dbt mart models distribute across cube files. "Inlined" models are
joined into the domain cube's `sql:` block and have no cube file of their own.

| Domain       | Cube file(s)                                                                            | dbt models inlined into SQL                                                                                                                                                                                             |
| ------------ | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| conformed    | dates, locations, regions, terms, school_calendars                                      | —                                                                                                                                                                                                                       |
| students     | students (Type 1), student_enrollments                                                  | dim_student_contact_persons, bridge_student_contacts                                                                                                                                                                    |
| staff        | staff (Type 1), staff_work_history, staff_compensation, staff_attrition, staff_benefits | dim_staff_status, dim_work_assignment_status, dim_work_assignment_jobs, dim_work_assignment_types, dim_work_assignment_locations, dim_work_assignment_organizational_units, dim_work_assignment_reporting_relationships |
| attendance   | attendance, attendance_interventions, attendance_streaks                                | dim_student_attendance_intervention_types                                                                                                                                                                               |
| behavioral   | behavioral, family_communications                                                       | —                                                                                                                                                                                                                       |
| gradebook    | grades_term, grades_gpa, grades_category, grades_assignments                            | —                                                                                                                                                                                                                       |
| assessment   | assessment_scores, assessment_scores_student_scoped                                     | dim_assessments, dim_assessment_comparisons, dim_assessment_targets, dim_student_assessment_expectations                                                                                                                |
| observations | observations, observation_scores, observation_microgoals                                | dim_staff_observation_rubrics, dim_staff_observation_rubric_measurements, dim_staff_observation_types, dim_staff_observation_microgoal_types, dim_staff_observation_expectations                                        |
| surveys      | surveys, survey_responses                                                               | dim_surveys, dim_survey_administrations, dim_survey_questions, bridge_survey_questions, dim_survey_expectations                                                                                                         |
| college      | college                                                                                 | dim_colleges                                                                                                                                                                                                            |
| talent       | talent                                                                                  | dim_job_postings, dim_job_candidates                                                                                                                                                                                    |
| staffing     | staffing                                                                                | —                                                                                                                                                                                                                       |
| support      | support                                                                                 | —                                                                                                                                                                                                                       |

**Note on staffing:** `dim_staffing_positions` has no joinable ID to
`dim_staff_work_assignments` (SmartRecruiters and ADP/Seat Tracker have no
shared key per the star schema spec). The staffing cube is standalone.

## Cube Patterns

### `sql_table:` vs `sql:` — when to use each

Use `sql_table:` whenever the cube maps to a single dbt model with no JOINs
needed in the SQL. Cube generates the SELECT internally; dimension `sql:` fields
are the explicit column references. A column rename in dbt breaks immediately
with a clear BigQuery error pointing to the exact dimension — no silent
failures.

Use `sql:` only when JOINs or window functions are required (inlining lookup
dims, period intersection). When you do, always enumerate columns explicitly —
never use wildcard aliases (`f.*`, `table.*`, `SELECT *`). A wildcard silently
drops renamed columns from the result set without failing at parse time;
explicit references fail loudly at query time and point directly to the broken
dimension.

**Rule:** `sql_table:` by default. `sql:` with explicit column list when JOINs
are unavoidable.

### Keeping Cube in sync when dbt column names change

There is no automatic cross-tool check out of the box. Three layers of
protection cover it:

**Layer 1 — dbt contracts (already enforced)** All `dim_*` and `fct_*` models
have `contract: enforced: true`. Renaming a column requires updating the
properties YAML or the dbt build fails in CI. That required edit is the natural
moment to check whether any Cube YAML in `src/cube/model/` references the old
column name. Treat the contract YAML diff in PR review as the signal: if a
column name changes there, grep `src/cube/model/` for it.

**Layer 2 — Cube query-time errors (reactive)** With explicit column references
in every `sql:` field, a broken reference produces a clear BigQuery error the
first time someone queries that dimension — not a silent wrong result. It points
directly to the broken field.

**Layer 3 — `cube validate` in CI (target state)** Cube's `cube validate`
command parses all YAML and dry-runs the SQL against the warehouse. Adding this
step to the CI pipeline catches broken column references at merge time, before
they reach production. This should be wired up as part of the infrastructure
work — it is the right long-term answer and removes the manual grep step from PR
review.

**Analyst-facing name vs. source column name** The Cube `name:` field (what
analysts see in the UI and API) and the `sql:` field (the BigQuery column
reference) are independent. A dbt column rename requires updating `sql:` only —
the analyst-facing `name:` is stable. Renaming a field in the UI requires
updating `name:` only — no BigQuery query changes. Keep these two concerns
separate when reviewing rename PRs.

### Pattern 1 — Conformed cubes

Thin wrappers exposing a single dbt model's columns as dimensions. No
`measures:` and no `joins:` — other cubes declare joins to conformed cubes on
their side. The five conformed cubes (`dates`, `locations`, `regions`, `terms`,
`school_calendars`) exist to be shared as join targets across all domains.

`dim_dates` is the only exception: it adds a `date_day` time dimension using the
`date_timestamp` column because Cube requires TIMESTAMP for time dimensions.
`dim_staff` and `dim_students` follow the same thin-wrapper shape but live in
their domain folders since they also serve as the base for domain-level queries.

**Reference: `conformed/locations.yml`**

```yaml
cubes:
  - name: dim_locations
    sql_table: kipptaf_marts.dim_locations

    dimensions:
      - name: location_id
        sql: location_id
        type: number
        primary_key: true

      - name: location_name
        sql: location_name
        type: string

      - name: location_abbreviation
        sql: location_abbreviation
        type: string

      - name: location_region
        sql: location_region
        type: string

      - name: location_grade_band
        sql: location_grade_band
        type: string
```

### Pattern 2 — Fact-based domain cubes

Fact tables have a date on every row. Use `sql_table`. Join `dim_dates` by
equating the fact's date column to `dim_dates.date_day` — no period intersection
needed. Domain-specific lookup dims that are used by exactly one parent are
inlined into the cube's `sql:` via JOIN rather than getting their own file.

**Reference: `attendance/attendance.yml`**

```yaml
cubes:
  - name: attendance
    sql_table: kipptaf_marts.fct_student_attendance_daily

    joins:
      - name: dim_dates
        sql: "{dim_dates.date_day} = CAST({CUBE}.attendance_date AS TIMESTAMP)"
        relationship: many_to_one

      - name: dim_locations
        sql: "{dim_locations.location_id} = {CUBE}.location_id"
        relationship: many_to_one

      - name: dim_students
        sql: |
          {dim_students.student_number} = {CUBE}.student_number
        relationship: many_to_one

    dimensions:
      - name: attendance_key
        sql: attendance_key
        type: string
        primary_key: true

      - name: attendance_date
        sql: CAST(attendance_date AS TIMESTAMP)
        type: time

      - name: is_absent
        sql: is_absent
        type: number

      - name: is_present
        sql: is_present
        type: number

      - name: is_tardy
        sql: is_tardy
        type: number

      - name: membership_value
        sql: membership_value
        type: number

    measures:
      - name: avg_daily_attendance
        description: Average Daily Attendance
        sql: is_present
        type: avg
        format: percent
        filters:
          - sql: "{CUBE}.membership_value = 1"

      - name: count_students
        sql: student_number
        type: count_distinct
        filters:
          - sql: "{CUBE}.membership_value = 1"
```

### Pattern 3 — SCD2 period intersection domain cubes

Used when the domain has no single event date per row — instead, data represents
a state valid for a range (e.g., "this employee had this job title from date A
to date B"). Multiple Type 2 child tables are joined via overlapping date
conditions; composite `effective_date_start` / `effective_date_end` are computed
with `GREATEST` / `LEAST`. A single `BETWEEN` join to `dim_dates` slices all
attributes to the same point in time.

**Why period intersection is required:** Cube's join engine does not guarantee
that independently-chained SCD2 tables are sliced to the same date. Joining
`dim_work_assignment_jobs` and `dim_work_assignment_locations` as separate cubes
would allow them to resolve to different effective periods for the same query,
producing incorrect headcount results. Period intersection in the cube `sql:`
eliminates this by computing the overlap explicitly before Cube sees the data.

**Anchor:** `dim_staff_work_assignments` (Type 1 — one row per current work
assignment). All Type 2 children join via `work_assignment_key`. Worker-level
status (`dim_staff_status`) joins via `dim_staff`.

**INNER vs LEFT JOIN:** Use INNER JOIN when a missing child record should drop
the row (e.g., an employee with no job record should not appear in headcount).
Use LEFT JOIN when the child is optional context (e.g.,
`dim_work_assignment_reporting_relationships` — absence of a manager FK should
not exclude the employee).

**Primary key rule:** No surrogate key spans the period-intersection rows. Use
`CONCAT(employee_number, '|', effective_date_start)` — unique per row since an
employee cannot have two different overlapping states at the same start date.

**Reference: `staff/staff_work_history.yml`**

```yaml
cubes:
  - name: staff_work_history
    sql: |
      SELECT
        swa.work_assignment_key,
        swa.employee_number,
        swa.full_time_equivalence_ratio,
        swa.management_position_indicator,
        ss.status_name,
        wj.job_title,
        wj.job_code__code_value     AS job_code,
        wt.worker_type_code__name   AS worker_type,
        wo.department_name,
        wo.business_unit_name,
        wl.location_code            AS work_location_code,
        GREATEST(
          ss.effective_date_start,
          wj.effective_date_start,
          wt.effective_date_start,
          wo.effective_date_start,
          wl.effective_date_start
        ) AS effective_date_start,
        LEAST(
          ss.effective_date_end,
          wj.effective_date_end,
          wt.effective_date_end,
          wo.effective_date_end,
          wl.effective_date_end
        ) AS effective_date_end
      FROM kipptaf_marts.dim_staff_work_assignments swa
      JOIN kipptaf_marts.dim_staff s
        ON swa.staff_key = s.staff_key
      JOIN kipptaf_marts.dim_staff_status ss
        ON ss.staff_key = s.staff_key
      JOIN kipptaf_marts.dim_work_assignment_jobs wj
        ON wj.work_assignment_key = swa.work_assignment_key
        AND ss.effective_date_start < wj.effective_date_end
        AND ss.effective_date_end   > wj.effective_date_start
      JOIN kipptaf_marts.dim_work_assignment_types wt
        ON wt.work_assignment_key = swa.work_assignment_key
        AND ss.effective_date_start < wt.effective_date_end
        AND ss.effective_date_end   > wt.effective_date_start
      JOIN kipptaf_marts.dim_work_assignment_organizational_units wo
        ON wo.work_assignment_key = swa.work_assignment_key
        AND wo.assignment_type = 'Primary'
        AND ss.effective_date_start < wo.effective_date_end
        AND ss.effective_date_end   > wo.effective_date_start
      JOIN kipptaf_marts.dim_work_assignment_locations wl
        ON wl.work_assignment_key = swa.work_assignment_key
        AND ss.effective_date_start < wl.effective_date_end
        AND ss.effective_date_end   > wl.effective_date_start

    joins:
      - name: dim_dates
        sql: >
          {dim_dates.date_day} BETWEEN CAST({CUBE}.effective_date_start AS
          TIMESTAMP) AND CAST({CUBE}.effective_date_end AS TIMESTAMP)
        relationship: many_to_one

      - name: dim_locations
        sql: "{dim_locations.location_abbreviation} = {CUBE}.work_location_code"
        relationship: many_to_one

      - name: dim_staff
        sql: "{dim_staff.employee_number} = {CUBE}.employee_number"
        relationship: many_to_one

    dimensions:
      - name: staff_work_history_key
        sql: >
          CONCAT(
            CAST({CUBE}.employee_number AS STRING), '|',
            CAST({CUBE}.effective_date_start AS STRING)
          )
        type: string
        primary_key: true

      - name: status_name
        sql: status_name
        type: string

      - name: job_title
        sql: job_title
        type: string

      - name: worker_type
        sql: worker_type
        type: string

      - name: department_name
        sql: department_name
        type: string

      - name: business_unit_name
        sql: business_unit_name
        type: string

      - name: effective_date_start
        sql: CAST(effective_date_start AS TIMESTAMP)
        type: time

    measures:
      - name: count_headcount
        description: Distinct active employees
        sql: employee_number
        type: count_distinct
        filters:
          - sql: "{CUBE}.status_name = 'Active'"

      - name: sum_fte
        description: Total FTE of active primary assignments
        sql: full_time_equivalence_ratio
        type: sum
        filters:
          - sql: "{CUBE}.status_name = 'Active'"
          - sql: "{CUBE}.management_position_indicator = false"
```

## Views

Two views per domain. Views select which fields from the domain cube and its
joins are exposed to consumers, and enforce the detail/summary access split.

**Detail view:** Exposes individual-row identifiers (employee_number,
student_number), all grouping dimensions, and all measures. PII fields are
present but hidden from users without the relevant PII access group.

**Summary view:** Exposes only measures and grouping dimensions. No individual
identifiers (no employee_number, student_number, or names). No `date_day` — too
granular for summary consumers.

**Reference: `views/staff/staff_detail.yml` and `staff_summary.yml`**

```yaml
# staff_detail.yml
views:
  - name: staff_detail

    cubes:
      - join_path: staff_work_history
        includes:
          - count_headcount
          - sum_fte
          - status_name
          - job_title
          - worker_type
          - department_name
          - business_unit_name

      - join_path: staff_work_history.dim_dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name

      - join_path: staff_work_history.dim_locations
        prefix: true
        includes:
          - location_name
          - location_abbreviation
          - location_region

      - join_path: staff_work_history.dim_staff
        prefix: true
        includes:
          - employee_number
          - formatted_name # PII — excluded by default, see access_policy
          - work_email # PII

    access_policy:
      - role: "*"
        member_level:
          includes: []
      - role: "detail-access"
        member_level:
          includes: "*"
          excludes:
            - dim_staff_formatted_name
            - dim_staff_work_email
      - role: "cube-access-staff-pii"
        member_level:
          includes: "*"
```

```yaml
# staff_summary.yml
views:
  - name: staff_summary

    cubes:
      - join_path: staff_work_history
        includes:
          - count_headcount
          - sum_fte
          - status_name
          - job_title
          - worker_type
          - department_name
          - business_unit_name

      - join_path: staff_work_history.dim_dates
        prefix: true
        includes:
          - academic_year
          - month_name

      - join_path: staff_work_history.dim_locations
        prefix: true
        includes:
          - location_name
          - location_abbreviation
          - location_region

    access_policy:
      - role: "*"
        member_level:
          includes: []
      - role: "summary-access"
        member_level:
          includes: "*"
```

## Access Policy Patterns

Three patterns applied consistently across all domains. These implement Layer 3
of the security model from the infrastructure spec — column-level visibility.
Layers 1 and 2 (identity resolution, row-level filtering) live in `cube.js`.

### Detail vs summary enforcement

`contextToGroups` in `cube.js` emits two synthetic roles alongside real Google
group names:

- Any `*-detail` group → add `detail-access`
- Any `*-detail` or `*-summary` group → add `summary-access`

Detail views gate on `detail-access`. Summary views gate on `summary-access`. A
user with `cube-school-bold-detail` gets both synthetic roles and can query
either view. A user with `cube-region-newark-summary` gets only `summary-access`
and cannot see detail views. A user with no scope groups sees nothing.

This approach keeps access policy rules DRY: one rule per view instead of one
rule per school/region group.

### Pattern 1 — PII fields

Present in the detail view field list, hidden from users without the PII group.
Default deny on the specific fields; PII group restores full access.

```yaml
# applied on detail views that include staff PII
access_policy:
  - role: "detail-access"
    member_level:
      includes: "*"
      excludes:
        - dim_staff_formatted_name
        - dim_staff_work_email
        - dim_staff_personal_email
        - dim_staff_personal_cell
  - role: "cube-access-staff-pii"
    member_level:
      includes: "*"
```

```yaml
# applied on detail views that include student PII
access_policy:
  - role: "detail-access"
    member_level:
      includes: "*"
      excludes:
        - dim_students_contact_name
        - dim_students_contact_phone
        - dim_students_birth_date
  - role: "cube-access-student-pii"
    member_level:
      includes: "*"
```

### Pattern 2 — Compensation fields

Applied on the staff detail and summary views for salary and pay rate
dimensions. Compensation fields are excluded from both views by default; only
users with the compensation access group see them.

```yaml
access_policy:
  - role: "detail-access"
    member_level:
      includes: "*"
      excludes:
        - base_pay_rate
        - annual_salary
        - pay_frequency
  - role: "cube-access-staff-compensation"
    member_level:
      includes: "*"
```

### Pattern 3 — Student domain visibility

`queryRewrite` in `cube.js` removes all student-domain views from schema
introspection for users without `cube-access-student-data` — that is the primary
enforcement. As belt-and-suspenders, all student-domain views (attendance,
assessment, gradebook, behavioral, surveys, students) carry:

```yaml
access_policy:
  - role: "*"
    member_level:
      includes: []
  - role: "cube-access-student-data"
    member_level:
      includes: "*"
```

## Domain Reference Implementations

One reference YAML per domain showing the structural pattern. Field lists are
abbreviated — full enumeration is the implementation plan's responsibility.

### Students

`students.yml` — Type 1 conformed wrapper. Follows Pattern 1 exactly: thin
`sql_table` wrapper with no measures and no joins declared. PII fields
(`formatted_name`, `birth_date`, `personal_email`, `personal_cell`) are present
as dimensions but gated in any view that includes them via Pattern 1 access
policy with `cube-access-student-pii`.

`student_enrollments.yml` — SCD2 domain cube. `dim_student_enrollments` has
`effective_date_start` and `effective_date_end`; the BETWEEN join to `dim_dates`
makes headcount queryable at any point in time. `dim_students` joins in as the
conformed Type 1 wrapper for demographics.

```yaml
cubes:
  - name: student_enrollments
    sql_table: kipptaf_marts.dim_student_enrollments

    joins:
      - name: dim_dates
        sql: >
          {dim_dates.date_day} BETWEEN CAST({CUBE}.enrollment_start_date AS
          TIMESTAMP) AND CAST({CUBE}.enrollment_end_date AS TIMESTAMP)
        relationship: many_to_one

      - name: dim_locations
        sql: "{dim_locations.location_id} = {CUBE}.location_id"
        relationship: many_to_one

      - name: dim_students
        sql: "{dim_students.student_number} = {CUBE}.student_number"
        relationship: many_to_one

    dimensions:
      - name: enrollment_key
        sql: enrollment_key
        type: string
        primary_key: true

      - name: grade_level
        sql: grade_level
        type: number

      - name: enroll_status
        sql: enroll_status
        type: number

      - name: academic_year
        sql: academic_year
        type: number

    measures:
      - name: count_headcount
        description: Distinct enrolled students
        sql: student_number
        type: count_distinct
        filters:
          - sql: "{CUBE}.enroll_status = 0"
```

### Staff

See Pattern 3 — SCD2 period intersection reference above (`staff_work_history`).

### Assessment

`assessment_scores.yml` — fact-based. `fct_assessment_scores_enrollment_scoped`
already carries `assessment_title` and `subject_area` — no `dim_assessments`
join needed for those fields. `dim_assessment_targets` is inlined for
proficiency benchmark data not present on the fact. Join key between fact and
targets is `assessment_key` (not `assessment_id`).

```yaml
cubes:
  - name: assessment_scores
    sql: |
      SELECT
        f.assessment_score_key,
        f.student_number,
        f.test_date,
        f.assessment_key,
        f.assessment_title,
        f.subject_area,
        f.scale_score,
        f.percent_correct,
        f.proficiency_level,
        f.is_mastery,
        f.region,
        t.target_name,
        t.target_category,
        t.benchmark_value
      FROM kipptaf_marts.fct_assessment_scores_enrollment_scoped f
      LEFT JOIN kipptaf_marts.dim_assessment_targets t
        ON f.assessment_key = t.assessment_key
        AND f.scale_score BETWEEN t.score_min AND t.score_max

    joins:
      - name: dim_dates
        sql: "{dim_dates.date_day} = CAST({CUBE}.test_date AS TIMESTAMP)"
        relationship: many_to_one

      - name: dim_locations
        sql: "{dim_locations.location_abbreviation} = {CUBE}.region"
        relationship: many_to_one

      - name: dim_students
        sql: "{dim_students.student_number} = {CUBE}.student_number"
        relationship: many_to_one

    dimensions:
      - name: assessment_score_key
        sql: assessment_score_key
        type: string
        primary_key: true

      - name: assessment_title
        sql: assessment_title
        type: string

      - name: subject_area
        sql: subject_area
        type: string

      - name: proficiency_level
        sql: proficiency_level
        type: string

      - name: scale_score
        sql: scale_score
        type: number

    measures:
      - name: avg_scale_score
        sql: scale_score
        type: avg

      - name: count_testers
        sql: student_number
        type: count_distinct
```

### Attendance

See Pattern 2 — fact-based reference above (`attendance`).

### Behavioral

`behavioral.yml` — fact-based. Incidents and consequences are joined in the cube
SQL. **Note for implementation:** verify that `fct_behavioral_consequences` is
truly one-to-one with `fct_behavioral_incidents` before using a LEFT JOIN — if
one incident can have multiple consequence rows, the join multiplies rows and
measure counts will be incorrect. If many-to-many, consequences should be a
separate cube file.

```yaml
cubes:
  - name: behavioral
    sql: |
      SELECT
        i.behavioral_incident_key,
        i.student_number,
        i.location_id,
        i.incident_date,
        i.incident_type,
        i.incident_category,
        c.consequence_type,
        c.consequence_start_date,
        c.consequence_end_date,
        c.consequence_duration
      FROM kipptaf_marts.fct_behavioral_incidents i
      LEFT JOIN kipptaf_marts.fct_behavioral_consequences c
        ON i.behavioral_incident_key = c.behavioral_incident_key

    joins:
      - name: dim_dates
        sql: "{dim_dates.date_day} = CAST({CUBE}.incident_date AS TIMESTAMP)"
        relationship: many_to_one

      - name: dim_locations
        sql: "{dim_locations.location_id} = {CUBE}.location_id"
        relationship: many_to_one

      - name: dim_students
        sql: "{dim_students.student_number} = {CUBE}.student_number"
        relationship: many_to_one

    dimensions:
      - name: behavioral_incident_key
        sql: behavioral_incident_key
        type: string
        primary_key: true

      - name: incident_type
        sql: incident_type
        type: string

      - name: incident_category
        sql: incident_category
        type: string

      - name: consequence_type
        sql: consequence_type
        type: string

    measures:
      - name: count_incidents
        sql: behavioral_incident_key
        type: count_distinct

      - name: count_students_with_incidents
        sql: student_number
        type: count_distinct
```

### Gradebook

`grades_term.yml` — fact-based, section-enrollment grain. Each grades fact FKs
to `dim_student_section_enrollments`, which FKs up to `dim_student_enrollments`
and `dim_course_sections`. Conformed dims are reached via chain traversal.

```yaml
cubes:
  - name: grades_term
    sql_table: kipptaf_marts.fct_grades_term

    joins:
      - name: dim_dates
        sql: "{dim_dates.date_day} = CAST({CUBE}.grade_date AS TIMESTAMP)"
        relationship: many_to_one

      - name: dim_locations
        sql: "{dim_locations.location_id} = {CUBE}.location_id"
        relationship: many_to_one

      - name: dim_students
        sql: "{dim_students.student_number} = {CUBE}.student_number"
        relationship: many_to_one

    dimensions:
      - name: grades_term_key
        sql: grades_term_key
        type: string
        primary_key: true

      - name: course_name
        sql: course_name
        type: string

      - name: term_name
        sql: term_name
        type: string

      - name: letter_grade
        sql: letter_grade
        type: string

      - name: grade_value
        sql: grade_value
        type: number

    measures:
      - name: avg_grade
        sql: grade_value
        type: avg

      - name: count_students
        sql: student_number
        type: count_distinct
```

### Observations

`observations.yml` — fact-based. `fct_staff_observations` already carries
`rubric_name` and `observation_type` directly — no dim joins needed. Use
`sql_table:` with explicit dimension column references.

```yaml
cubes:
  - name: observations
    sql_table: kipptaf_marts.fct_staff_observations

    joins:
      - name: dim_dates
        sql: "{dim_dates.date_day} = CAST({CUBE}.observed_at_date AS TIMESTAMP)"
        relationship: many_to_one

      - name: dim_locations
        sql: "{dim_locations.location_id} = {CUBE}.location_id"
        relationship: many_to_one

      - name: dim_staff
        sql: "{dim_staff.employee_number} = {CUBE}.teacher_employee_number"
        relationship: many_to_one

    dimensions:
      - name: staff_observation_key
        sql: staff_observation_key
        type: string
        primary_key: true

      - name: rubric_name
        sql: rubric_name
        type: string

      - name: observation_type
        sql: observation_type
        type: string

    measures:
      - name: count_observations
        sql: staff_observation_key
        type: count_distinct

      - name: count_observed_staff
        sql: teacher_employee_number
        type: count_distinct
```

### Surveys

`surveys.yml` — fact-based. Survey dims are inlined; `bridge_survey_questions`
is also inlined to avoid the unlabeled diamond subgraph flagged in the star
schema spec (two paths to `dim_surveys` without the bridge).

```yaml
cubes:
  - name: surveys
    sql: |
      SELECT
        ss.survey_submission_key,
        ss.survey_administration_key,
        ss.date_submitted,
        ss.respondent_employee_number,
        ss.respondent_population,
        sa.administration_name,
        sa.academic_year      AS survey_academic_year,
        s.survey_title,
        s.survey_type
      FROM kipptaf_marts.fct_survey_submissions ss
      LEFT JOIN kipptaf_marts.dim_survey_administrations sa
        ON ss.survey_administration_key = sa.survey_administration_key
      LEFT JOIN kipptaf_marts.dim_surveys s
        ON sa.survey_id = s.survey_id

    joins:
      - name: dim_dates
        sql: "{dim_dates.date_day} = CAST({CUBE}.date_submitted AS TIMESTAMP)"
        relationship: many_to_one

    dimensions:
      - name: survey_submission_key
        sql: survey_submission_key
        type: string
        primary_key: true

      - name: survey_title
        sql: survey_title
        type: string

      - name: administration_name
        sql: administration_name
        type: string

      - name: respondent_population
        sql: respondent_population
        type: string

    measures:
      - name: count_submissions
        sql: survey_submission_key
        type: count_distinct

      - name: count_respondents
        sql: respondent_employee_number
        type: count_distinct
```

### College

`college.yml` — SCD2 enrollment period cube. `dim_college_enrollments` records
enrollment spans (`start_date_key` / `end_date_key`); the BETWEEN join to
`dim_dates` makes enrollment queryable at any point in time. `dim_colleges` is
inlined via natural key `college_code_branch`.

```yaml
cubes:
  - name: college
    sql: |
      SELECT
        ce.college_enrollment_key,
        ce.student_number,
        ce.college_code_branch,
        ce.start_date_key,
        ce.end_date_key,
        ce.enrollment_status,
        ce.degree_pursued,
        ce.degree_title,
        ce.is_graduated,
        ce.is_withdrawn,
        c.college_name,
        c.college_type,
        c.state_code
      FROM kipptaf_marts.dim_college_enrollments ce
      LEFT JOIN kipptaf_marts.dim_colleges c
        ON ce.college_code_branch = c.college_code_branch

    joins:
      - name: dim_dates
        sql: >
          {dim_dates.date_day} BETWEEN CAST({CUBE}.start_date_key AS TIMESTAMP)
          AND CAST({CUBE}.end_date_key AS TIMESTAMP)
        relationship: many_to_one

      - name: dim_students
        sql: "{dim_students.student_number} = {CUBE}.student_number"
        relationship: many_to_one

    dimensions:
      - name: college_enrollment_key
        sql: college_enrollment_key
        type: string
        primary_key: true

      - name: college_name
        sql: college_name
        type: string

      - name: college_type
        sql: college_type
        type: string

      - name: enrollment_status
        sql: enrollment_status
        type: string

    measures:
      - name: count_enrolled
        sql: student_number
        type: count_distinct
```

### Talent

`talent.yml` — fact-based. Candidate and posting dims inlined; no joinable ID to
`dim_staff_work_assignments` so talent is standalone (per star schema spec).

```yaml
cubes:
  - name: talent
    sql: |
      SELECT
        a.job_candidate_application_key,
        a.job_candidate_key,
        a.job_posting_key,
        a.new_date,
        a.job_title,
        a.department_internal,
        a.job_city,
        a.application_state,
        a.application_status,
        a.candidate_source,
        a.candidate_source_type,
        p.posting_title,
        p.posting_status,
        c.candidate_name
      FROM kipptaf_marts.fct_job_candidate_applications a
      LEFT JOIN kipptaf_marts.dim_job_postings p
        ON a.job_posting_key = p.job_posting_key
      LEFT JOIN kipptaf_marts.dim_job_candidates c
        ON a.job_candidate_key = c.job_candidate_key

    joins:
      - name: dim_dates
        sql: "{dim_dates.date_day} = CAST({CUBE}.new_date AS TIMESTAMP)"
        relationship: many_to_one

    dimensions:
      - name: job_candidate_application_key
        sql: job_candidate_application_key
        type: string
        primary_key: true

      - name: job_title
        sql: job_title
        type: string

      - name: application_state
        sql: application_state
        type: string

    measures:
      - name: count_applications
        sql: job_candidate_application_key
        type: count_distinct

      - name: count_candidates
        sql: job_candidate_key
        type: count_distinct
```

### Staffing

`staffing.yml` — standalone dim, no fact joins. `dim_staffing_positions` has no
joinable ID to `dim_staff_work_assignments`.

```yaml
cubes:
  - name: staffing
    sql_table: kipptaf_marts.dim_staffing_positions

    joins:
      - name: dim_locations
        sql: "{dim_locations.location_id} = {CUBE}.location_id"
        relationship: many_to_one

    dimensions:
      - name: staffing_position_key
        sql: staffing_position_key
        type: string
        primary_key: true

      - name: position_title
        sql: position_title
        type: string

      - name: position_status
        sql: position_status
        type: string

      - name: position_type
        sql: position_type
        type: string

    measures:
      - name: count_positions
        sql: staffing_position_key
        type: count_distinct

      - name: count_open_positions
        sql: staffing_position_key
        type: count_distinct
        filters:
          - sql: "{CUBE}.position_status = 'Open'"
```

### Support

`support.yml` — simple fact table.

```yaml
cubes:
  - name: support
    sql_table: kipptaf_marts.fct_support_tickets

    joins:
      - name: dim_dates
        sql: "{dim_dates.date_day} = CAST({CUBE}.created_date AS TIMESTAMP)"
        relationship: many_to_one

      - name: dim_staff
        sql: "{dim_staff.employee_number} = {CUBE}.requester_employee_number"
        relationship: many_to_one

    dimensions:
      - name: ticket_key
        sql: ticket_key
        type: string
        primary_key: true

      - name: ticket_type
        sql: ticket_type
        type: string

      - name: ticket_status
        sql: ticket_status
        type: string

      - name: priority
        sql: priority
        type: string

    measures:
      - name: count_tickets
        sql: ticket_key
        type: count_distinct

      - name: count_open_tickets
        sql: ticket_key
        type: count_distinct
        filters:
          - sql: "{CUBE}.ticket_status != 'Closed'"
```
