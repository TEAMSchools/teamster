# Cube Model YAML Design

**Date:** 2026-04-17 **Status:** Draft

## Overview

Define the YAML conventions, patterns, and reference implementations for the
Cube semantic layer model files that sit on top of the infrastructure
established in the
[Cube infrastructure spec](2026-04-15-cube-infrastructure-design.md). This spec
covers how the dbt mart models from `models/marts/` map to cube files, the cube
naming convention that drives automatic security enforcement, how SCD Type 2
tables are handled for point-in-time queries, the five access policy patterns
applied across views, and how the detail/summary access split is enforced via
views and access policies. Where `cube.js` behavior directly governs YAML
decisions (e.g., how naming convention drives `queryRewrite`), it is documented
here; `cube.js` auth and infrastructure setup are in the infrastructure spec.

## Goals

- Clear conventions for when a dbt model becomes its own cube file vs gets
  inlined into a parent cube's SQL
- A reusable pattern for SCD2 period intersection that makes headcount-over-time
  and any other snapshot query correct at any point in time
- Two consumer-facing views per domain (detail and summary) with access policies
  that enforce the three-layer security model from the infrastructure spec
- Reference YAML for each of the three structural patterns (conformed dim,
  fact-based domain cube, SCD2 period intersection) so engineers have a working
  template for all remaining domain implementations

## Non-goals

- Full field enumeration for all models — implementation plan
- Pre-aggregations — follow-up spec
- Downstream integrations (Tableau, Superset, Streamlit) — follow-up spec
- `cube.js` auth, environment setup, and MCP configuration — covered in the
  infrastructure spec

## Design Decisions

### One cube file per domain, not one per dbt model

Cube's join engine does not guarantee independently-chained SCD2 cubes are
sliced to the same date. Separate cubes for `dim_work_assignment_jobs` and
`dim_work_assignment_locations` could resolve to different effective periods,
producing incorrect headcount results. Period intersection in the domain cube's
`sql:` block eliminates this by computing the overlap before Cube sees the data.

### Period intersection lives in Cube SQL, not dbt

SCD2 children could have been pre-joined in a dbt snapshot. That re-introduces
the one-big-table pattern the star schema was designed to avoid and duplicates
logic Cube already owns. dbt handles structural transformations and stable
business rules; Cube owns presentation-layer shaping.

### SCD2 period intersection: GREATEST/LEAST and LEFT JOIN constraint

`GREATEST` across all SCD2 children's `effective_start_date` and `LEAST` across
their `effective_end_date` yields the overlap window — the period when all
attributes held simultaneously. A single `BETWEEN` join to `dim_dates` slices
that window to any point in time. `GREATEST`/`LEAST` return NULL if any argument
is NULL, so only INNER-joined children contribute date columns.
`dim_work_assignment_primary` is LEFT JOINed (not every assignment has a
primary-indicator record) and its dates are therefore excluded from the
computation.

### Strict-chain traversal: facts join direct FK parents only

Facts declare joins only to their immediate FK parents (e.g., gradebook →
`dim_student_enrollments`, not `dim_students`). Deeper context is reached via
join path traversal in views. This mirrors the dbt star schema and prevents
diamond paths that cause Cube to double-count rows.

### Role-playing FK dimensions: always denormalize the secondary role

Some fact tables have two foreign keys pointing to the same dimension —
`fct_staff_observations` has `teacher_staff_key` (the teacher being observed)
and `observer_staff_key` (the observer), both referencing `dim_staff`. In SQL
you'd join `dim_staff` twice under different aliases. Cube doesn't allow that —
you can only declare one join per named cube.

The correct resolution is always denormalization: add the secondary role's key
attributes (name, key, etc.) directly to the shared dimension. Join `dim_staff`
once on the primary FK; the secondary role's attributes are available on the
same row without a second join. The gradebook cube is the canonical example —
`manager_name` and `manager_staff_key` are added to `dim_staff` (#3838) so both
teacher and manager attributes are accessible via a single join. Observations
(`observer_staff_key`) and surveys (`subject_staff_key`) follow the same
pattern.

### Date joins use `date_day` (TIMESTAMP), not `date_key` (DATE)

`dim_dates` exposes `date_key` (DATE, PK) and `date_day` (TIMESTAMP, time
dimension). Cube requires `type: time` dimensions to be TIMESTAMP. All join
conditions use `{dates.date_day}` with `CAST({CUBE}.<date_fk> AS TIMESTAMP)` to
keep both sides of the join type-consistent.

### PII column metadata and descriptions sourced from dbt

**dbt is the source of truth for PII classification and dimension descriptions —
not Cube YAML.**

dbt mart properties already carry `config.meta.contains_pii: true` on sensitive
columns and populated `description:` fields on all columns. Cube dimensions
should reflect this metadata rather than duplicate or diverge from it.

**PII flags — first pass:** When implementing any domain cube, open the source
dbt model's property YAML and check each column for
`config.meta.contains_pii: true`. For every matching column, add
`meta: {pii: true}` to the corresponding Cube dimension. Do this on the first
pass — do not defer it. Automation via #3727 (open) will eventually generate
these flags and access policy annotations from the dbt manifest, but until that
lands the tagging is manual.

**Descriptions — first pass:** Do not hand-author `description:` fields on Cube
dimensions. Metadata sync (#3764, live) populates them automatically from dbt
column descriptions. Any description written in Cube YAML will be overwritten by
sync.

**dbt `config.meta` example (source of truth):**

```yaml
# in dim_students.yml (dbt)
- name: lea_student_identifier
  data_type: int64
  description: KIPP's own SIS identifier for the student...
  config:
    meta:
      contains_pii: true
```

**Cube dimension (derived):**

```yaml
# in students/students.yml (Cube) — meta and description sourced from dbt
- name: lea_student_identifier
  sql: lea_student_identifier
  type: number
  meta:
    pii: true
```

Tag any dimension whose dbt source column has `contains_pii: true`, or that
contains sensitive demographic data visible at base access level (race, gender,
disability status) that downstream tools should handle with care.

Do not tag quasi-identifiers (grade level, zip code, school assignment) — fields
that become identifying only in combination for small populations. That risk is
managed by the summary/detail view split and BI-layer cell suppression, not
column metadata.

Tag location is always the cube dimension, not the view include list. Views
select from cubes and inherit the signal without re-declaring it.

### Two views per domain: detail and summary

Each domain exposes a detail view and a summary view. Detail consumers see
individual-record dimensions including identifiers and optionally PII; summary
consumers see only aggregate-safe dimensions and measures with no individual
identifiers. The split keeps access policy rules DRY — one rule per view rather
than one per school/region/role combination. `date_day` is included in summary
views — time-series analysis (week-over-week trends, score trajectories,
headcount over time) is a core consumer need even at the summary level. Privacy
protection in summary views comes from removing individual identifiers, not from
removing dates. For SCD2 cubes, BI tools must apply a date filter before
querying — without one, each employment period fans out to one row per day.

## Cube Naming Convention

| Domain           | Pattern                                          | Examples                                                                      |
| ---------------- | ------------------------------------------------ | ----------------------------------------------------------------------------- |
| Student dim/fact | `students` (base), `student_<name>` (all others) | `students`, `student_enrollments`, `student_attendance`, `student_ell_status` |
| Staff dim/fact   | `staff` (base), `staff_<name>` (all others)      | `staff`, `staff_attrition`, `staff_observations`, `staff_work_history`        |
| Conformed dims   | bare business name                               | `dates`, `locations`, `regions`, `terms`, `school_calendars`                  |
| Views            | `<domain>_<grain>`                               | `attendance_detail`, `attendance_summary`                                     |

`queryRewrite` in `cube.js` uses `isStudentMember` (`startsWith("student")`) and
`isStaffMember` (`startsWith("staff")`) to enforce access controls. Following
the naming convention is what makes a new cube automatically subject to the
right permission check — no static array to update.

`sql_table:` points at the BigQuery table name, which retains its `dim_`/`fct_`
prefix. The cube name and the table name are independent.

## Repository Structure

```text
src/cube/model/
  cubes/
    conformed/
      dates.yml             # cube: dates        (sql_table: dim_dates)
      locations.yml         # cube: locations    (sql_table: dim_locations)
      regions.yml           # cube: regions      (sql_table: dim_regions)
      terms.yml             # cube: terms        (sql_table: dim_terms)
      school_calendars.yml  # cube: school_calendars (sql_table: dim_school_calendars)
    students/
      students.yml                        # cube: students              (sql_table: dim_students)
      student_enrollments.yml             # cube: student_enrollments   (sql_table: dim_student_enrollments)
      student_ell_status.yml              # cube: student_ell_status    (sql_table: dim_student_ell_status)
      student_iep_status.yml              # cube: student_iep_status    (sql_table: dim_student_iep_status)
      student_meal_eligibility_status.yml # cube: student_meal_eligibility_status
    staff/
      staff.yml                      # cube: staff                   (sql_table: dim_staff)
      staff_work_history.yml         # cube: staff_work_history      (SCD2 period intersection)
      staff_compensation.yml         # cube: staff_compensation
      staff_additional_earnings.yml  # cube: staff_additional_earnings
      staff_attrition.yml            # cube: staff_attrition
      staff_benefits.yml             # cube: staff_benefits
      staff_memberships.yml          # cube: staff_memberships
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
      observation_goals.yml
    surveys/
      surveys.yml
      survey_responses.yml
      survey_expectations.yml
    postsecondary/
      postsecondary.yml
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
    postsecondary/
      postsecondary_detail.yml
      postsecondary_summary.yml
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

Total cube files: ~41 (down from 72 dbt models). Views: 24 (2 per domain × 12
non-conformed domains).

## Domain Breakdown

How the dbt mart models distribute across cube files. "Inlined" models are
joined into the domain cube's `sql:` block and have no cube file of their own.

| Domain       | Cube file(s)                                                                                                                          | Primary dbt model(s)                                                                                                                                                                                    | dbt models inlined into SQL                                                                                                                                                                                                                          |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| conformed    | dates, locations, regions, terms, school_calendars                                                                                    | dim_dates, dim_locations, dim_regions, dim_terms, dim_school_calendars                                                                                                                                  | —                                                                                                                                                                                                                                                    |
| students     | students (Type 1), student_enrollments, student_ell_status, student_iep_status, student_meal_eligibility_status                       | dim_students, dim_student_enrollments, dim_student_ell_status, dim_student_iep_status, dim_student_meal_eligibility_status                                                                              | dim_student_contact_persons, bridge_student_contacts                                                                                                                                                                                                 |
| staff        | staff (Type 1), staff_work_history, staff_compensation, staff_additional_earnings, staff_attrition, staff_benefits, staff_memberships | dim_staff, dim_staff_work_assignments, fct_work_assignment_compensation, fct_work_assignment_additional_earnings, fct_staff_attrition, fct_staff_benefits_enrollments, fct_staff_membership_enrollments | dim_staff_status, dim_work_assignment_status, dim_work_assignment_primary, dim_work_assignment_jobs, dim_work_assignment_types, dim_work_assignment_locations, dim_work_assignment_organizational_units, dim_work_assignment_reporting_relationships |
| attendance   | attendance, attendance_interventions, attendance_streaks                                                                              | fct_student_attendance_daily, fct_student_attendance_interventions, fct_student_attendance_streaks                                                                                                      | dim_student_attendance_intervention_types                                                                                                                                                                                                            |
| behavioral   | behavioral, family_communications                                                                                                     | fct_behavioral_incidents, fct_family_communications                                                                                                                                                     | fct_behavioral_consequences                                                                                                                                                                                                                          |
| gradebook    | grades_term, grades_gpa, grades_category, grades_assignments                                                                          | fct_grades_term, fct_grades_gpa, fct_grades_category, fct_grades_assignments                                                                                                                            | dim_courses, dim_course_sections, dim_student_section_enrollments, bridge_course_section_teachers, bridge_course_section_terms                                                                                                                       |
| assessment   | assessment_scores, assessment_scores_student_scoped, assessment_administrations                                                       | fct_assessment_scores_enrollment_scoped, fct_assessment_scores_student_scoped, dim_assessment_administrations                                                                                           | dim_assessments, dim_assessment_comparisons, dim_assessment_goals, bridge_assessment_expectations_enrollment_scoped, bridge_assessment_expectations_student_scoped                                                                                   |
| observations | observations, observation_scores, observation_goals                                                                                   | fct_staff_observations, fct_staff_observation_scores, fct_staff_observation_goals                                                                                                                       | dim_staff_observation_rubrics, dim_staff_observation_rubric_measurements, dim_staff_observation_types, dim_staff_observation_goal_types, dim_staff_observation_expectations                                                                          |
| surveys      | surveys, survey_responses, survey_expectations                                                                                        | fct_survey_submissions, fct_survey_responses, bridge_survey_expectations                                                                                                                                | dim_surveys, dim_survey_administrations, dim_survey_questions, bridge_survey_questions                                                                                                                                                               |
| college      | college                                                                                                                               | dim_college_enrollments                                                                                                                                                                                 | dim_colleges                                                                                                                                                                                                                                         |
| talent       | talent                                                                                                                                | fct_job_candidate_applications                                                                                                                                                                          | dim_job_postings, dim_job_candidates                                                                                                                                                                                                                 |
| staffing     | staffing                                                                                                                              | dim_staffing_positions                                                                                                                                                                                  | —                                                                                                                                                                                                                                                    |
| support      | support                                                                                                                               | fct_support_tickets                                                                                                                                                                                     | —                                                                                                                                                                                                                                                    |

**Note on student status dims (added 2026-05):** Three point-in-time SCD2 status
dims were added to the students domain: `dim_student_ell_status`,
`dim_student_iep_status`, and `dim_student_meal_eligibility_status`. All three
start with `student_` and are automatically covered by `isStudentMember` in
`cube.js`, requiring `cube-access-student-data`. They follow Pattern 3 — SCD2
period intersection — joined to `dim_dates` via the `BETWEEN` range join
(`one_to_many` relationship). They are surfaced via the attendance views where
ELL/IEP/meal-eligibility breakdowns are a primary consumer need.

**Note on staffing:** `dim_staffing_positions` has no joinable ID to
`dim_staff_work_assignments` (SmartRecruiters and ADP/Seat Tracker have no
shared key per the star schema spec). The staffing cube is standalone.

**Note on survey_expectations:** `bridge_survey_expectations` has a different
grain from `fct_survey_submissions` (one row per expected respondent ×
administration vs one row per submission). It must be its own cube file
(`survey_expectations.yml`) — inlining it into the surveys cube would produce a
fanout. The bridge is its own cube joined to `fct_survey_submissions` via LEFT
JOIN for completion-rate analysis.

**Note on dim_work_assignment_primary:** Tracks `is_primary_position` as an SCD2
on `work_assignment_key` with `effective_start_date` / `effective_end_date`.
Included in the `staff_work_history` period intersection when primary-position
filtering is needed at a point in time. See Pattern 3 for the optional LEFT JOIN
pattern.

**Note on gradebook — teacher and manager info:** Inlining
`bridge_course_section_teachers` surfaces `teacher_staff_key` on the gradebook
cube, enabling a join to `dim_staff` for teacher name. Manager name requires
`manager_name` and `manager_staff_key` to be denormalized onto `dim_staff`
(#3838) — Cube cannot join `dim_staff` twice under different roles. Implement
gradebook cubes after #3838 merges.

**Note on observations — eligible teacher denominator:** `pct_evaluated` and
`pct_assigned_goals` require a count of eligible teachers as the denominator.
This is not on `fct_staff_observations` — requires an `is_teaching_role` flag or
documented filter on `dim_staff_work_assignments` (#3839) before implementation.

**Note on courses:** There is no courses domain cube or view.
`dim_student_section_enrollments`, `dim_courses`, `dim_course_sections`,
`bridge_course_section_teachers`, and `bridge_course_section_terms` are
dimension-only models with no natural measures — no fact table backs them.
Course/section attributes are inlined into the gradebook cubes, which are the
primary analytical consumers of section-level data.

**Note on assessment domain (updated 2026-04):**
`dim_student_assessment_expectations` no longer exists — it was deleted and
replaced by two bridge models:
`bridge_assessment_expectations_enrollment_scoped` (internal assessments, joins
via `student_section_enrollment_key`) and
`bridge_assessment_expectations_student_scoped` (K-8 replacement-curriculum
assessments, joins via `student_key`). `dim_assessment_administrations` is a new
standalone dimension (not inlined) with FK from both fact tables via
`assessment_administration_key`. The `assessment_administrations` cube file
should be added to the repository structure.

`fct_assessment_scores_enrollment_scoped` has `is_mastery`;
`fct_assessment_scores_student_scoped` now also has `is_mastery` (added 2026-05,
unblocked #3840). Mastery-rate measures are implementable on both fact tables.

**Note on surveys — role-playing respondent FKs:** `fct_survey_submissions` uses
a respondent-type discriminator (`staff`, `student`, `family`) with role-playing
FKs: `staff_key` → `dim_staff`, `student_enrollment_key` →
`dim_student_enrollments`, `student_contact_person_key` →
`dim_student_contact_persons`. Manager surveys also carry `subject_staff_key`
(the manager being evaluated) as a second FK to `dim_staff` — same role-playing
FK pattern as `observer_staff_key` in observations. Both are resolved by
denormalizing subject/observer attributes onto `dim_staff` (same approach as
#3838). All three respondent FK columns carry `meta: {pii: true}`.

**Note on talent:** `dim_job_candidates` (inlined into the talent cube) contains
candidate PII (name, email, contact details). The talent views require
`cube-access-staff-pii` or a dedicated `cube-access-talent` group — to be
decided at implementation. Candidate data is not covered by FERPA or employment
law but is sensitive personal data governed by general privacy best practices.
`fct_job_candidate_applications.phone_interview_score` is now typed `int64`
(fixed 2026-05, #3837 resolved). `avg_phone_interview_score` is implementable.

**Note on college (postsecondary) domain:** `dim_college_enrollments` only
covers enrollment status, degree, major, `is_graduated`, and `is_withdrawn`. The
majority of postsecondary metrics (FAFSA, FSA IDs, HESAA, application tracking,
ECC scores, award letters, college GPA, career launch) require
KIPPADB/Salesforce models not yet in `models/marts/`. Implement only the
measures backed by `dim_college_enrollments` now; remaining metrics are blocked
on #3695.

**Note on support:** `fct_support_tickets` may reference staff or student
identifiers depending on the ticket subject. Access group requirements depend on
which identifier fields are exposed — to be confirmed at implementation against
the model's column list.

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

### Renaming `name:` fields when BI tools are connected

Once a BI tool (Tableau, Superset, Streamlit, etc.) is connected to a Cube view,
the `name:` field is a public API. Renaming it breaks any saved report,
dashboard, or query that references the old name — the field silently drops or
returns "not found".

**Rule: treat view `name:` fields as stable contracts once a BI tool is
connected. Do not rename without coordinating with BI consumers first.**

Three options when a rename is unavoidable:

**Option 1 — Deprecation window** Keep the old `name:` in the view alongside the
new one temporarily. Communicate the cutover date to BI consumers, remove the
old name after dashboards are updated.

**Option 2 — Views as the stable interface (structural mitigation)** This is the
strongest argument for the two-view pattern. Analysts connect BI tools to
`staff_detail` / `staff_summary` views, not directly to cubes. A `name:` change
inside the cube can be remapped in the view without touching the field name the
BI tool sees — the view `name:` stays stable even if the underlying cube
dimension is reorganized.

**Option 3 — Cube aliases** Cube does not have a native field deprecation
mechanism today. Until it does, Option 1 or Option 2 are the available paths.

**Internal vs. external `name:` fields** Cube `name:` fields are internal — safe
to rename freely before any BI tool connects. View `name:` fields are external
once a downstream consumer exists — coordinate before changing. Document which
views have active BI connections in the exposure YAML (`models/exposures/`) so
the boundary is visible in PR review.

### Pattern 1 — Conformed cubes

Thin wrappers exposing a single dbt model's columns as dimensions. No
`measures:` and no `joins:` — other cubes declare joins to conformed cubes on
their side. The five conformed cubes (`dates`, `locations`, `regions`, `terms`,
`school_calendars`) exist to be shared as join targets across all domains.

The `dates` cube is the only exception: it adds a `date_day` time dimension
using the `date_timestamp` column because Cube requires TIMESTAMP for time
dimensions. The `date_key` column (DATE) is the primary key used for
deduplication. All join conditions use `{dates.date_day}` (the TIMESTAMP column)
so that Cube's time filter parameters — which generate TIMESTAMP comparisons —
are type-consistent throughout. Fact FK columns (DATE) are cast to TIMESTAMP at
the join site: `CAST({CUBE}.<date_fk_column> AS TIMESTAMP)`.

**Reference: `conformed/dates.yml`**

```yaml
cubes:
  - name: dates
    sql_table: kipptaf_marts.dim_dates

    dimensions:
      - name: date_key
        sql: date_key
        type: string
        primary_key: true

      - name: date_day
        sql: date_timestamp
        type: time

      - name: academic_year
        sql: academic_year
        type: number

      - name: fiscal_year
        sql: fiscal_year
        type: number

      - name: month_name
        sql: month_name
        type: string

      - name: month_number
        sql: month_number
        type: number

      - name: year_number
        sql: year_number
        type: number

      - name: is_weekday
        sql: is_weekday
        type: boolean
```

**Reference: `conformed/locations.yml`**

```yaml
cubes:
  - name: locations
    sql_table: kipptaf_marts.dim_locations

    joins:
      - name: regions
        sql: "{regions.region_key} = {CUBE}.region_key"
        relationship: many_to_one

    dimensions:
      - name: location_key
        sql: location_key
        type: string
        primary_key: true

      - name: region_key
        sql: region_key
        type: string

      - name: location_name
        sql: name
        type: string

      - name: location_abbreviation
        sql: abbreviation
        type: string

      - name: location_grade_band
        sql: grade_band
        type: string

      - name: location_campus
        sql: campus
        type: string

      - name: is_campus
        sql: is_campus
        type: boolean
```

`dim_staff` and `dim_students` follow the same thin-wrapper shape but live in
their domain folders since they also serve as the base for domain-level queries.

### Pattern 2 — Fact-based domain cubes

Fact tables have a date FK on every row (`date_key`, `observed_date_key`,
`creation_date_key`, etc. — all raw DATE matching `dim_dates.date_key`). Use
`sql_table`. Join `dim_dates` by equating the fact's date FK to
`dim_dates.date_key`. Join all other dimensions via their surrogate key FK
columns — never via natural keys or denormalized attributes. Strict-chain rule
applies: facts join only their direct FK parents; deeper context (e.g.,
`dim_regions` via `dim_locations`) is reached by traversing the chain in the
Cube view join path.

**Reference: `attendance/attendance.yml`**

```yaml
cubes:
  - name: student_attendance
    public: false
    sql_table: kipptaf_marts.fct_student_attendance_daily

    joins:
      - name: dates
        sql: "{dates.date_day} = CAST({CUBE}.date_key AS TIMESTAMP)"
        relationship: many_to_one

      - name: locations
        sql: "{locations.location_key} = {CUBE}.location_key"
        relationship: many_to_one

      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

      - name: terms
        sql: "{terms.term_key} = {CUBE}.term_key"
        relationship: many_to_one

    dimensions:
      - name: student_attendance_daily_key
        sql: student_attendance_daily_key
        type: string
        primary_key: true

      - name: attendance_date
        sql: CAST(date_key AS TIMESTAMP)
        type: time
        public: true

      - name: attendance_category
        sql: attendance_category
        type: string
        public: true

      - name: is_absent
        sql: is_absent
        type: number
        public: true

      - name: is_present
        sql: is_present
        type: number
        public: true

      - name: is_tardy
        sql: is_tardy
        type: number
        public: true

      - name: membership_value
        sql: membership_value
        type: number
        public: true

      - name: attendance_value
        sql: attendance_value
        type: number
        public: true

    measures:
      - name: avg_daily_attendance
        description: Average Daily Attendance
        sql: attendance_value
        type: avg
        format: percent
        public: true
        filters:
          - sql: "{CUBE}.membership_value = 1"

      - name: count_students
        sql: student_enrollment_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.membership_value = 1"
```

**Note on school_calendars:** `fct_student_attendance_daily` joins
`dim_school_calendars` via compound key `(date_key, location_key)` to avoid a
diamond path through `dim_locations`. Declare this join in the cube as a
separate join target — do not route through `dim_locations` for school-calendar
attributes.

### Pattern 3 — SCD2 period intersection domain cubes

Used when the domain has no single event date per row — instead, data represents
a state valid for a range (e.g., "this employee had this job title from date A
to date B"). Multiple Type 2 child tables are joined via overlapping date
conditions; composite `effective_start_date` / `effective_end_date` are computed
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
status (`dim_staff_status`) joins via `staff_key`. All SCD2 date columns are
named `effective_start_date` / `effective_end_date`.

**INNER vs LEFT JOIN:** Use INNER JOIN when a missing child record should drop
the row (e.g., an employee with no job record should not appear in headcount).
Use LEFT JOIN when the child is optional context (e.g.,
`dim_work_assignment_reporting_relationships` — absence of a manager FK should
not exclude the employee). `dim_work_assignment_primary` is LEFT JOIN since not
all work assignments may have a primary-indicator record.

**Join order:** `dim_staff_work_assignments` anchors the FROM clause.
`dim_staff_status` is joined first and acts as the **controlling SCD2**: all
subsequent overlap conditions are written against its `effective_start_date` /
`effective_end_date`. It joins directly on `swa.staff_key` — no intermediate
`dim_staff` join is needed in the SQL block (`dim_staff` appears only in
`joins:` for Cube view traversal). The four work assignment SCD2 children
(`jobs`, `types`, `org_units`, `locations`) follow in arbitrary order, each
overlap-filtered against `ss`. `dim_work_assignment_primary` is LEFT JOINed
last. `dim_staff_status` is the controlling period because employment status
spans the broadest date range — a narrower child as anchor would inadvertently
drop rows where that child has no overlapping record.

**`effective_end_date` sentinel:** Open-ended records use `9999-12-31`, not
NULL. The overlap conditions (`ss.effective_start_date < wj.effective_end_date`
etc.) are therefore safe without `COALESCE` — NULL would make the comparison
evaluate to NULL and silently drop active employees.

**`dim_dates` relationship is `one_to_many`:** One work history row spans a date
range and matches many `dim_dates` rows. This is the reverse of the
equality-join case (`many_to_one`). Always apply a date filter in queries
against this cube — without one, each work history row fans out to one result
row per day in its effective range.

**Location join gap:** `dim_work_assignment_locations` tracks `location_code`
but has no `location_key` FK to `dim_locations`. The `dim_locations` join cannot
be declared here — location context for staff is limited to `work_location_code`
as a string dimension until a `location_key` FK is added to
`dim_work_assignment_locations` in dbt. Deferred to implementation.

**Primary key rule:** No surrogate key spans the period-intersection rows. Use
`CONCAT(staff_key, '|', effective_start_date)` — unique per row since an
employee cannot have two different overlapping states at the same start date.

**Reference: `staff/staff_work_history.yml`**

```yaml
cubes:
  - name: staff_work_history
    public: false
    sql: |
      SELECT
        swa.work_assignment_key,
        swa.staff_key,
        swa.full_time_equivalency,
        swa.is_management_position,
        ss.status_name,
        wj.position_title,
        wj.job_code,
        wt.worker_type_name            AS worker_type,
        wo.department_name,
        wo.business_unit_name,
        wl.location_code               AS work_location_code,
        wp.is_primary_position,
        GREATEST(
          ss.effective_start_date,
          wj.effective_start_date,
          wt.effective_start_date,
          wo.effective_start_date,
          wl.effective_start_date
        ) AS effective_start_date,
        LEAST(
          ss.effective_end_date,
          wj.effective_end_date,
          wt.effective_end_date,
          wo.effective_end_date,
          wl.effective_end_date
        ) AS effective_end_date
      FROM kipptaf_marts.dim_staff_work_assignments swa
      JOIN kipptaf_marts.dim_staff_status ss
        ON ss.staff_key = swa.staff_key
      JOIN kipptaf_marts.dim_work_assignment_jobs wj
        ON wj.work_assignment_key = swa.work_assignment_key
        AND ss.effective_start_date < wj.effective_end_date
        AND ss.effective_end_date   > wj.effective_start_date
      JOIN kipptaf_marts.dim_work_assignment_types wt
        ON wt.work_assignment_key = swa.work_assignment_key
        AND ss.effective_start_date < wt.effective_end_date
        AND ss.effective_end_date   > wt.effective_start_date
      JOIN kipptaf_marts.dim_work_assignment_organizational_units wo
        ON wo.work_assignment_key = swa.work_assignment_key
        AND wo.assignment_type = 'Primary'
        AND ss.effective_start_date < wo.effective_end_date
        AND ss.effective_end_date   > wo.effective_start_date
      JOIN kipptaf_marts.dim_work_assignment_locations wl
        ON wl.work_assignment_key = swa.work_assignment_key
        AND ss.effective_start_date < wl.effective_end_date
        AND ss.effective_end_date   > wl.effective_start_date
      LEFT JOIN kipptaf_marts.dim_work_assignment_primary wp
        ON wp.work_assignment_key = swa.work_assignment_key
        AND ss.effective_start_date < wp.effective_end_date
        AND ss.effective_end_date   > wp.effective_start_date

    joins:
      - name: dates
        sql: >
          {dates.date_day} BETWEEN CAST({CUBE}.effective_start_date AS
          TIMESTAMP) AND CAST({CUBE}.effective_end_date AS TIMESTAMP)
        relationship: one_to_many

      - name: staff
        sql: "{staff.staff_key} = {CUBE}.staff_key"
        relationship: many_to_one

    dimensions:
      - name: staff_work_history_key
        sql: >
          CONCAT(
            CAST({CUBE}.staff_key AS STRING), '|',
            CAST({CUBE}.effective_start_date AS STRING)
          )
        type: string
        primary_key: true

      - name: status_name
        sql: status_name
        type: string
        public: true

      - name: position_title
        sql: position_title
        type: string
        public: true

      - name: worker_type
        sql: worker_type
        type: string
        public: true

      - name: department_name
        sql: department_name
        type: string
        public: true

      - name: business_unit_name
        sql: business_unit_name
        type: string
        public: true

      - name: is_primary_position
        sql: is_primary_position
        type: boolean
        public: true

      - name: effective_start_date
        sql: CAST(effective_start_date AS TIMESTAMP)
        type: time
        public: true

    measures:
      - name: count_headcount
        description: Distinct active employees
        sql: staff_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.status_name = 'Active'"

      - name: sum_fte
        description: Total FTE of active assignments
        sql: full_time_equivalency
        type: sum
        public: true
        filters:
          - sql: "{CUBE}.status_name = 'Active'"
```

**Column names to verify at implementation:** exact aliases for `job_code`,
`worker_type_name`, and `location_code` on the SCD2 child tables — read each
child model's property YAML before writing the SELECT list. The
`dim_work_assignment_primary` LEFT JOIN adds `wp.effective_start_date` and
`wp.effective_end_date` to the date range but those are excluded from the
GREATEST/LEAST shown above since NULL from a LEFT JOIN would collapse the entire
result in BigQuery. Add them to the GREATEST/LEAST only when the join is
converted to INNER.

### Member visibility

All domain cubes set `public: false` at the cube level. Cube treats this as
cascading — every member (dimension, measure, segment) inherits `public: false`
unless explicitly overridden.

**Rule:** every member listed in any view `includes:` must declare
`public: true`. Add it in the same step as writing the view — a missing
`public: true` is only detected at query time as a "hidden member" error, not at
schema load.

Two exceptions do not need `public: true`:

- **Primary key dimensions** — never included in view `includes:` lists.
- **Internal helper measures** (prefixed `_`) — used only as sub-expressions
  inside other measures; stay hidden via the cascade.

Conformed dimension cubes do **not** set `public: false`. They are never queried
directly — members are always accessed through a domain cube join path — and
member `public` defaults to `true`.

## Views

Two views per domain. Views select which fields from the domain cube and its
joins are exposed to consumers, and enforce the detail/summary access split.

**Detail view:** Exposes individual-row identifiers (staff_key, student_key),
all grouping dimensions, and all measures. PII fields are present but hidden
from users without the relevant PII access group.

**Summary view:** Exposes only measures and grouping dimensions. No individual
identifiers (no staff_key, student_key, or names). `date_day` is included —
time-series analysis is a core consumer need at the summary level. Privacy
protection comes from removing individual identifiers, not dates.

**`prefix: true` and access policy names:** When a join path uses
`prefix: true`, Cube prepends the cube name to every field in that block's
`includes:` list. A field named `full_name` in the `staff` cube becomes
`staff_full_name` in the view namespace. `access_policy` `excludes:` entries
must use the post-prefix names — that is why the exclude list says
`staff_full_name`, not `full_name`.

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
          - position_title
          - worker_type
          - department_name
          - business_unit_name

      - join_path: staff_work_history.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name

      - join_path: staff_work_history.staff
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - birth_date
          - work_email
          - google_email
          - personal_email
          - personal_cell_phone
          - active_directory_username
          - staff_unique_id
          - gender_identity
          - race
          - is_hispanic

    access_policy:
      - role: "detail-access"
        member_level:
          includes: "*"
          excludes:
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_birth_date
            - staff_work_email
            - staff_google_email
            - staff_personal_email
            - staff_personal_cell_phone
            - staff_active_directory_username
            - staff_staff_unique_id
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
          - position_title
          - worker_type
          - department_name
          - business_unit_name

      - join_path: staff_work_history.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name

    access_policy:
      - role: "summary-access"
        member_level:
          includes: "*"
```

## Access Policy Patterns

Five patterns applied consistently across all domains. These implement Layer 3
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

### Access group reference

All named access groups used across views, with their scope and the pattern that
implements them.

| Group                            | Type                                     | Scope                                                                                                                                                                                                                                                                   | Pattern                       |
| -------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| `detail-access`                  | Synthetic (emitted by `contextToGroups`) | Grants access to all detail views; applied to any user with a `*-detail` Google group                                                                                                                                                                                   | Detail vs summary enforcement |
| `summary-access`                 | Synthetic (emitted by `contextToGroups`) | Grants access to all summary views; applied to any user with a `*-detail` or `*-summary` Google group                                                                                                                                                                   | Detail vs summary enforcement |
| `cube-access-student-data`       | Google group                             | Required to see any student-domain cube members (attendance, assessment, gradebook, behavioral, surveys, students, student status dims). Primary enforcement via `queryRewrite` `isStudentMember` check (`startsWith("student")`); access policy is belt-and-suspenders | Pattern 3                     |
| `cube-access-student-pii`        | Google group                             | Unlocks student direct identifiers (name, DOB, LEA/state/district IDs, Salesforce contact ID, contact name/phone) on detail views                                                                                                                                       | Pattern 1                     |
| `cube-access-staff-pii`          | Google group                             | Unlocks staff direct identifiers and sensitive HR narratives (name, DOB, emails, phone, AD username, employee number, termination reason/date) on detail views                                                                                                          | Pattern 1                     |
| `cube-access-staff-compensation` | Google group                             | Unlocks pay rate fields (annual wage, hourly wage, daily rate, period rate, additional earnings) on staff compensation views                                                                                                                                            | Pattern 2                     |
| `cube-access-staff-benefits`     | Google group                             | Unlocks benefits enrollment fields (plan type, plan name, coverage level) on staff benefits views                                                                                                                                                                       | Pattern 4                     |
| `cube-access-staff-observations` | Google group                             | Unlocks individual observation records, scores, and free-text feedback fields on observations detail views; row-level scoping to own school enforced separately via `queryRewrite`                                                                                      | Pattern 5                     |

### Pattern 1 — PII fields

Present in the detail view field list, hidden from users without the PII group.
Default deny on the specific fields; PII group restores full access.

**Staff PII** — direct identifiers and sensitive HR narratives gated by
`cube-access-staff-pii`. All carry `meta: {pii: true}` on the cube dimension.

```yaml
# applied on detail views that include staff PII
access_policy:
  - role: "detail-access"
    member_level:
      includes: "*"
      excludes:
        - staff_full_name
        - staff_first_name
        - staff_last_name
        - staff_birth_date
        - staff_work_email
        - staff_google_email
        - staff_personal_email
        - staff_personal_cell_phone
        - staff_active_directory_username
        - staff_staff_unique_id
        - termination_reason
        - termination_effective_date
  - role: "cube-access-staff-pii"
    member_level:
      includes: "*"
```

**Student PII** — direct identifiers gated by `cube-access-student-pii`. All
carry `meta: {pii: true}` on the cube dimension.

```yaml
# applied on detail views that include student PII
access_policy:
  - role: "detail-access"
    member_level:
      includes: "*"
      excludes:
        - students_full_name
        - students_birth_date
        - students_lea_student_identifier
        - students_state_student_identifier
        - students_district_student_identifier
        - students_salesforce_contact_id
        - students_contact_name
        - students_contact_phone
  - role: "cube-access-student-pii"
    member_level:
      includes: "*"
```

**Sensitive demographics** — `meta: {pii: true}` tagged in the cube but visible
at base access level; not in any `excludes:` list. Included in both detail and
summary views for trend analysis. BI-layer cell suppression applies for small
populations.

- Students: `gender_identity`, `race`, `meal_eligibility_status`, `is_ell`,
  `has_iep`, `is_gifted`
- Staff: `gender_identity`, `race`, `is_hispanic`

### Pattern 2 — Compensation fields

Applied on the staff compensation and additional earnings views. Compensation
fields are excluded by default; only users with the compensation access group
see them. All carry `meta: {pii: true}` on the cube dimension.

Fields: `annual_wage`, `hourly_wage`, `daily_rate`, `period_rate` (from
`staff_compensation`); `rate_amount`, `earning_code`, `earning_description`
(from `staff_additional_earnings`).

```yaml
access_policy:
  - role: "detail-access"
    member_level:
      includes: "*"
      excludes:
        - annual_wage
        - hourly_wage
        - daily_rate
        - period_rate
        - rate_amount
        - earning_code
        - earning_description
  - role: "cube-access-staff-compensation"
    member_level:
      includes: "*"
```

### Pattern 3 — Student domain visibility

`queryRewrite` in `cube.js` strips all dimensions and measures whose cube name
starts with `student` (via `isStudentMember`) from queries for users without
`cube-access-student-data` — that is the primary enforcement. As
belt-and-suspenders, all student-domain views (attendance, assessment,
gradebook, behavioral, surveys, students) carry:

```yaml
access_policy:
  - role: "*"
    member_level:
      includes: []
  - role: "cube-access-student-data"
    member_level:
      includes: "*"
```

### Pattern 4 — Benefits fields

Applied on the staff benefits view. Benefits enrollment data can reveal health
information — plan type and coverage tier are proxies for health status and
family circumstances. Per ADA, benefits data must be treated separately from
general personnel records. All carry `meta: {pii: true}` on the cube dimension.

Fields: `plan_type`, `plan_name`, `coverage_level` (from `staff_benefits`).

```yaml
access_policy:
  - role: "detail-access"
    member_level:
      includes: "*"
      excludes:
        - plan_type
        - plan_name
        - coverage_level
  - role: "cube-access-staff-benefits"
    member_level:
      includes: "*"
```

### Pattern 5 — Observations (column gate + row-level scoping)

Observation data requires two independent layers of restriction beyond the base
detail/summary split.

**Column gate** (`cube-access-staff-observations`): Controls whether a user can
see individual observation records, scores, and free-text feedback at all.
Applied on the observations detail view. Fields gated: `score`,
`overall_rating`, `notes`, `positive_feedback`, `growth_areas`,
`text_box_content`, `response_text`. All carry `meta: {pii: true}` on the cube
dimension.

**Row-level scoping** (`queryRewrite` in `cube.js`): Users with
`cube-access-staff-observations` see individual records only for their own
school(s). For other schools, only aggregates are accessible. `queryRewrite`
reads the user's `locationKeys` claim (a list — APs covering multiple schools
get multiple values) from the security context and injects a
`{observations.location_key} IN (...)` filter when the query targets the detail
view. When the query targets the summary view, no filter is injected — aggregate
scores across all schools are visible. Users with a regional or org-wide scope
group get an empty `locationKeys` list, which `queryRewrite` treats as
unrestricted (no filter injected on either view).

The two layers are independent: a user without `cube-access-staff-observations`
sees nothing regardless of school assignment. The row filter only applies once
the column gate passes.

```yaml
# observations_detail.yml
access_policy:
  - role: "detail-access"
    member_level:
      includes: "*"
      excludes:
        - score
        - overall_rating
        - notes
        - positive_feedback
        - growth_areas
        - text_box_content
        - response_text
  - role: "cube-access-staff-observations"
    member_level:
      includes: "*"
```

Row-level school scoping is enforced in `cube.js` via `queryRewrite` — not in
the access policy. The access policy controls column visibility; `queryRewrite`
controls row visibility for users who pass the column gate.
