# Cube Model YAML Design

**Date:** 2026-04-17 **Status:** Active

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

### One cube per analytical grain, not one per dbt model

Each distinct analytical grain gets its own cube file. Ask three questions for
any dbt model:

**Does it have a distinct fact grain analysts query independently?** It gets its
own cube. Each fact table maps to one cube: `fct_student_attendance_daily` →
`student_attendance`, `fct_student_attendance_interventions` →
`student_attendance_interventions`. Multiple fact grains in a domain → multiple
cubes. Attendance has three; gradebook has four; observations has three.

**Is it a lookup dim or bridge with no independent analytical grain?** Inline it
into the parent cube's `sql:` block. `dim_courses`, `dim_survey_questions`,
`dim_assessments`, and all bridge tables fall here — they add attributes to a
parent but are never queried on their own.

**Is it part of an SCD2 cluster?** The anchor table gets the cube; all SCD2
children are inlined via period intersection (Pattern 3). They must all resolve
to the same point in time — independent SCD2 cubes would allow different
children to resolve to different effective periods for the same query, producing
incorrect results.

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

### Role-playing FK dimensions: use `extends` to create a role alias cube

Some fact tables have two foreign keys pointing to the same dimension —
`fct_staff_observations` has `teacher_staff_key` (the teacher being observed)
and `observer_staff_key` (the observer), both referencing `dim_staff`. In SQL
you'd join `dim_staff` twice under different aliases. Cube doesn't allow two
joins to the same named cube.

The correct resolution is `extends`: create a second cube that inherits all
dimensions from `staff` but carries a distinct name, backed by the same
`dim_staff` table. The fact cube then declares two joins — one to `staff` on the
primary FK, one to the role alias cube on the secondary FK. No dbt model changes
are required; role attributes stay where they belong, on a staff-shaped cube.

```yaml
cubes:
  - name: staff_manager # role alias — inherits all staff dimensions
    extends: staff
    public: false
```

**Naming constraint:** The extended cube must follow the `staff_<role>` naming
convention (e.g., `staff_manager`, `staff_observer`, `staff_survey_subject`).
`queryRewrite` in `cube.js` uses `startsWith("staff")` for `isStaffMember` — a
cube named `manager_staff` would not match and would bypass the staff security
filter entirely.

**Access policy in views:** A detail view including both a `staff` and a
`staff_manager` join path needs both sets of PII field names in the `excludes:`
list — prefixed `staff_*` from the `staff` join path and `staff_manager_*` from
the `staff_manager` join path (when `prefix: true`).

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

**Descriptions — first pass:** Metadata sync (#3764) is not yet live. Copy
`description:` from the source dbt model's property YAML when writing each
dimension. If the dbt column has no description in dbt, omit the field rather
than inventing one. When sync ships it will populate missing descriptions and
may overwrite hand-authored values — so exact wording matters less than
coverage. Measure descriptions have no dbt equivalent and must always be
hand-authored.

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
| Views            | `student_<domain>_<grain>` / `staff_<grain>`     | `student_attendance_detail`, `student_attendance_summary`, `staff_detail`     |

`queryRewrite` in `cube.js` uses `isStudentMember` (`startsWith("student")`) and
`isStaffMember` (`startsWith("staff")`) to enforce access controls. Following
the naming convention is what makes a new cube automatically subject to the
right permission check — no static array to update.

`sql_table:` points at the BigQuery table name, which retains its `dim_`/`fct_`
prefix. The cube name and the table name are independent.

## Domain Notes

**Note on student status dims (added 2026-05):** Three point-in-time SCD2 status
dims expose `is_ell`, `is_iep`, `iep_classification`, NJ sped codes,
`is_meal_eligible`, and `meal_eligibility` in both attendance views. Status
reflects the student's classification on the specific attendance date, not their
current status today.

Cube names: `student_ell_status`, `student_iep_status`,
`student_meal_eligibility_status` — all start with `student_` and are
automatically covered by `isStudentMember` in `cube.js`, requiring
`cube-access-student-data`. No `STUDENT_CUBES` entry needed.

Pattern 3 (SCD2 period intersection) was considered and rejected: it applies
when multiple SCD2 children can drift to different effective periods. The
attendance fact has one event date per row; all three status joins anchor to the
same `date_key`, so no period intersection is needed. Instead, three direct
`many_to_one` joins from `student_attendance`:

```yaml
sql: >
  {student_ell_status.student_enrollment_key} = {CUBE}.student_enrollment_key
  AND {CUBE}.date_key >= {student_ell_status.effective_date_start_key} AND
  {CUBE}.date_key <= {student_ell_status.effective_date_end_key}
relationship: many_to_one
```

`many_to_one` is safe because the dbt non-overlapping-spans uniqueness tests
guarantee at most one status row per enrollment per date. LEFT JOIN means dates
with no matching span return NULL — treated as not ELL / not IEP / not
meal-eligible in BI tools.

New dimensions are categorical status attributes (same tier as `race`,
`gender_identity`, `is_gifted`). No `access_policy` changes needed — they
inherit `*` under `cube-access-student-data` and are not direct identifiers
under FERPA.

Files:

| File                                                 | Change                                                                  |
| ---------------------------------------------------- | ----------------------------------------------------------------------- |
| `cubes/students/student_ell_status.yml`              | New                                                                     |
| `cubes/students/student_iep_status.yml`              | New                                                                     |
| `cubes/students/student_meal_eligibility_status.yml` | New                                                                     |
| `cubes/attendance/student_attendance.yml`            | 3 new joins                                                             |
| `views/attendance/student_attendance_detail.yml`     | Remove `dim_students.is_ell`; add 3 join paths + `meta.folders` entries |
| `views/attendance/student_attendance_summary.yml`    | Same                                                                    |

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

**Note on point-in-time manager resolver — `staff_reporting_relationships` +
`staff_manager`:**

"Who was the manager of this teacher/observer/subject on this date?" is a
three-table period intersection — not a single join. `staff_key` is not unique
in `dim_staff_work_assignments` (a person can hold multiple assignments), so the
primary assignment at date D must be resolved before the manager lookup; the
primary flag is itself SCD2, making this a genuine period intersection:

```text
primary assignment @ D          (dim_work_assignment_primary, SCD2)
  -> reporting relationship @ D (dim_work_assignment_reporting_relationships, SCD2)
    -> manager_staff_key         (role FK -> dim_staff via staff_manager alias)
```

Resolver cube is `staff_reporting_relationships` (`public: false`). The `staff_`
prefix keeps it under `queryRewrite`'s `startsWith("staff")` gate. Reference SQL
(validated against prod, 2026-05-28 — see full design spec
`docs/superpowers/specs/2026-05-28-staff-reporting-relationships-dim-design.md`):

```yaml
cubes:
  - name: staff_reporting_relationships
    public: false
    sql: |
      SELECT
        swa.staff_key,
        rr.manager_staff_key,
        GREATEST(wap.effective_start_date, rr.effective_start_date) AS effective_start_date,
        LEAST(wap.effective_end_date,      rr.effective_end_date)   AS effective_end_date
      FROM kipptaf_marts.dim_work_assignment_primary wap
      JOIN kipptaf_marts.dim_staff_work_assignments swa
        ON wap.work_assignment_key = swa.work_assignment_key
        AND swa.staff_key IS NOT NULL
      JOIN kipptaf_marts.dim_work_assignment_reporting_relationships rr
        ON rr.work_assignment_key = wap.work_assignment_key
        AND wap.effective_start_date <= rr.effective_end_date
        AND wap.effective_end_date   >= rr.effective_start_date
      WHERE wap.is_primary_position

    dimensions:
      - name: staff_reporting_relationship_key
        sql: >
          CONCAT(
            CAST({CUBE}.staff_key AS STRING), '|',
            CAST({CUBE}.effective_start_date AS STRING)
          )
        type: string
        primary_key: true

      - name: staff_key
        sql: staff_key
        type: string
        public: true

      - name: manager_staff_key
        sql: manager_staff_key
        type: string
        public: true

      - name: effective_start_date
        sql: CAST(effective_start_date AS TIMESTAMP)
        type: time
        public: true
```

**`staff_manager` role alias** inherits all `staff` dimensions; `staff_` prefix
keeps it in the `isStaffMember` gate (see Design Decision: role-playing FK
dimensions):

```yaml
cubes:
  - name: staff_manager
    extends: staff
    public: false
```

**Per-fact join** — each staff-keyed fact joins the resolver via an inclusive
`BETWEEN`. Substitute the fact's person FK (`teacher_staff_key`,
`observer_staff_key`, `subject_staff_key`) and date FK (`date_key`,
`observed_date_key`, `submitted_date_key`) as appropriate:

```yaml
joins:
  - name: staff_reporting_relationships
    relationship: many_to_one
    sql: >
      {staff_reporting_relationships.staff_key} = {CUBE}.<person_staff_key> AND
      CAST({CUBE}.<date_key> AS TIMESTAMP)
          BETWEEN CAST({staff_reporting_relationships.effective_start_date} AS
      TIMESTAMP)
          AND     CAST({staff_reporting_relationships.effective_end_date}   AS
      TIMESTAMP)

  - name: staff_manager
    sql:
      "{staff_manager.staff_key} =
      {staff_reporting_relationships.manager_staff_key}"
    relationship: many_to_one
```

`BETWEEN` is inclusive. These spans are end-dated to day-before-next-start, so
each record date matches exactly one span. Prod-validated: zero fan-out across
47,585 `fct_staff_observations` rows; 48 observations pre-date the teacher's
primary/reporting span and correctly resolve to NULL manager via LEFT JOIN.

**dbt guard test:**
`tests/dim_work_assignment_primary__no_overlapping_primary_spans.sql` (merged PR
#4067) asserts no staff has two overlapping primary spans — the invariant the
resolver grain depends on.

**Access policy note:** Views that expose `staff_manager` through the resolver
need both `staff_*` and `staff_manager_*` prefixed PII fields in the `excludes:`
list. `staff_reporting_relationships` adds no extra PII; `manager_staff_key` is
a surrogate.

**Note on gradebook — teacher and manager info:** Inlining
`bridge_course_section_teachers` surfaces `teacher_staff_key` on the gradebook
cube, enabling a join to `staff` for teacher name. Manager-at-date is resolved
via the `staff_reporting_relationships` point-in-time resolver + `staff_manager`
alias — see the manager resolver note above. #3838 is closed; this resolver
design supersedes the earlier direct-join approach.

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
assessments, joins via `student_key`). `dim_assessment_administrations` is a
standalone dimension (not inlined) with FK from both fact tables via
`assessment_administration_key`; it gets its own `assessment_administrations`
cube file.

`fct_assessment_scores_enrollment_scoped` has `is_mastery`;
`fct_assessment_scores_student_scoped` now also has `is_mastery` (added 2026-05,
unblocked #3840). Mastery-rate measures are implementable on both fact tables.

**Note on surveys — role-playing respondent FKs:** `fct_survey_submissions` uses
a respondent-type discriminator (`staff`, `student`, `family`) with role-playing
FKs: `staff_key` → `dim_staff`, `student_enrollment_key` →
`dim_student_enrollments`, `student_contact_person_key` →
`dim_student_contact_persons`. Manager surveys also carry `subject_staff_key`
(the manager being evaluated) as a second FK to `dim_staff` — same role-playing
FK pattern as `observer_staff_key` in observations. Both are resolved via
`extends`: create `staff_observer` and `staff_survey_subject` cubes extending
`staff`, joined on their respective secondary FKs. All three respondent FK
columns carry `meta: {pii: true}`.

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
        sql: "{CUBE}.`name`"
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
      - name: _sum_attendance_value
        sql: attendance_value
        type: sum
        public: false

      - name: _sum_membership_value
        sql: membership_value
        type: sum
        public: false

      - name: avg_daily_attendance
        description: >
          Average Daily Attendance (ADA) — SUM(attendance_value) /
          SUM(membership_value)
        sql: "{_sum_attendance_value} / NULLIF({_sum_membership_value}, 0)"
        type: number
        format: percent
        public: true

      - name: count_students
        sql: student_enrollment_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.membership_value = 1"
```

**Note on locations:** `student_attendance` has no direct `locations` join.
Location context is reached via `student_enrollments.locations` in the view
(`join_path: student_attendance.student_enrollments.locations`). Adding a direct
`locations` join alongside `student_enrollments` would create a diamond path —
both routes resolve to the same cube and Cube would double-count. Domains whose
fact table has `location_key` directly but no `student_enrollments` FK can use a
direct `locations` join safely.

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

### Pattern 4 — Snapshot cubes (cumulative daily-status flags)

Some fact tables have one row per entity per day where key columns are
**cumulative running statuses** — re-stamped on every row with the entity's
status as of that day. A canonical example: `is_chronically_absent` on
`fct_student_attendance_daily` is `true` on every day a student's YTD ADA is
below 90%, not just the day they crossed the threshold. Without a point-in-time
anchor, `count_distinct` on any such flag across a date range **overcounts** — a
student flagged on 30 days is counted 30 times.

**Two complementary mechanisms** guard against this class of error.

#### `queryRewrite` auto-injection (`SNAPSHOT_CUBES` / `SNAPSHOT_MEASURE_STEMS`)

`cube.js` maintains two arrays:

- `SNAPSHOT_CUBES` — list of cube `name:` values that have cumulative
  daily-status flags
- `SNAPSHOT_MEASURE_STEMS` — list of measure name stems (e.g.
  `"chronically_absent"`, `"truant"`) that are snapshot measures on those cubes

For any unanchored query against a snapshot measure, `queryRewrite` injects the
appropriate anchor automatically:

| Query shape                              | Anchor injected                                     |
| ---------------------------------------- | --------------------------------------------------- |
| No granularity, or `granularity: "year"` | `is_latest_record = true`                           |
| `granularity: "month"`                   | `is_month_end_record = true`                        |
| `granularity: "week"`                    | `is_week_end_record = true`                         |
| `granularity: "day"`                     | No injection — daily grain is already point-in-time |

Named `_year_end` / `_month_end` / `_week_end` measures bypass injection —
anchors are baked into their SQL `filters:`. Unsupported granularities (quarter)
and named period-end measures used without matching granularity both throw a
descriptive error.

**Cube requirements:** Any cube registered in `SNAPSHOT_CUBES` must expose three
boolean dimensions:

- `is_latest_record` — `true` on the entity's final membership day (year-end
  snapshot)
- `is_month_end_record` — `true` on the last full membership day per calendar
  month per enrollment
- `is_week_end_record` — `true` on the last full membership day per calendar
  week per enrollment

These are dbt-computed window function columns on the underlying fact table.

**To add a new domain with snapshot measures:**

1. Add the cube `name:` to `SNAPSHOT_CUBES` in `cube.js`
2. Add the snapshot measure name stems to `SNAPSHOT_MEASURE_STEMS`
3. Ensure the underlying dbt fact table provides `is_latest_record`,
   `is_month_end_record`, and `is_week_end_record`
4. Add the three dimensions to the cube YAML
5. Add named `_year_end`, `_month_end`, and `_week_end` measure variants with
   their denominators anchored to the same period (see `attendance.yml` as the
   reference implementation)

#### Named period-end measures

In addition to auto-injection, each snapshot measure family exposes three named
variants that bypass injection entirely (the anchor is in the measure SQL
`filters:`):

```yaml
- name: count_chronically_absent_year_end
  # ... filters: is_latest_record = true
- name: count_chronically_absent_month_end
  # ... filters: is_month_end_record = true
- name: count_chronically_absent_week_end
  # ... filters: is_week_end_record = true
```

Named variants are the correct choice for BI tool usage where `timeDimensions`
granularity is set to `"month"` or `"week"` — the BI tool controls the anchor
implicitly through its granularity choice, and named measures make that coupling
explicit.

**Granularity enforcement:** `_month_end` measures throw an error if used
without `timeDimensions` granularity `"month"`; `_week_end` requires `"week"`.
Without this guard, an unanchored `count_chronically_absent_month_end` over a
date range returns "CA at any month-end during the range" — a meaningful-looking
but wrong number.

#### Filter dimensions in views

Both `is_month_end_record` and `is_week_end_record` must be included in view
`includes:` lists (in addition to `is_latest_record`) and placed in a `Filter`
folder in `meta.folders`. This enables direct use as explicit filters in
contexts where `queryRewrite` injection is not active (e.g., SQL API, Superset
native queries).

#### Reference implementation

`src/cube/model/cubes/attendance/attendance.yml` is the first domain that
implements this pattern. It covers CA (`is_chronically_absent`, `pct_tier_1_2`,
`pct_tier_3`) and truancy (`is_truant`) measure families. Consult it as the
template when adding the pattern to a new domain.

---

### Member visibility

All cubes — domain and conformed — set `public: false` at the cube level. Cube
treats this as cascading: every member (dimension, measure, segment) inherits
`public: false` unless explicitly overridden.

**Rule:** every member listed in any view `includes:` must declare
`public: true`. Add it in the same step as writing the view — a missing
`public: true` is only detected at query time as a "hidden member" error, not at
schema load.

Two exceptions do not need `public: true`:

- **Primary key dimensions** — never included in view `includes:` lists.
- **Internal helper measures** (prefixed `_`) — used only as sub-expressions
  inside other measures; stay hidden via the cascade.

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
      - group: detail-access
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
      - group: cube-access-staff-pii
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
      - group: summary-access
        member_level:
          includes: "*"
```

## Access Policy Patterns

Five patterns applied consistently across all domains. These implement Layer 3
of the security model from the infrastructure spec — column-level visibility.
Layers 1 and 2 (identity resolution, row-level filtering) live in `cube.js`.

### Detail vs summary enforcement

`contextToGroups` in `cube.js` emits two synthetic groups alongside real Google
group names:

- Any `*-detail` group → add `detail-access`
- Any `*-detail` or `*-summary` group → add `summary-access`

Detail views gate on `group: detail-access`. Summary views gate on
`group: summary-access`. A user with `cube-school-bold-detail` gets both
synthetic groups and can query either view. A user with
`cube-region-newark-summary` gets only `summary-access` and cannot see detail
views. A user with no scope groups sees nothing.

**Tier is derived from the effective scope group only** (same priority as
`queryRewrite`: network > region > school). A lower-priority `-detail` group
cannot escalate access past what the effective scope grants — e.g., a user whose
effective scope is `cube-region-newark-summary` does not get `detail-access`
because they also happen to hold `cube-school-bold-detail`.

**These two access tiers are independent and additive.** Scope group tier
determines which view is accessible; `cube-access-student-data` membership
determines whether student-domain members appear inside that view (enforced by
`queryRewrite`). Both are required to see student data:

- Scope group only (no `cube-access-student-data`): view is accessible but
  `queryRewrite` strips all `student*` dimensions and measures — date, location,
  and term breakdowns remain, student breakdowns do not.
- `cube-access-student-data` only (no scope group): `withSyntheticGroups()`
  produces no synthetic groups, all views deny access, `queryRewrite` is never
  reached.
- Both: view accessible and student members visible.

The synthetic groups are not cached — `groupCache` stores only real Google
groups so `queryRewrite` lookups stay unaffected. `withSyntheticGroups()`
derives them fresh on every `contextToGroups` return.

This approach keeps access policy rules DRY: one rule per view instead of one
rule per school/region group.

### Access group reference

All named access groups used across views, with their scope and the pattern that
implements them.

| Group                            | Type                                     | Scope                                                                                                                                                                                                                                                              | Pattern                       |
| -------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- |
| `detail-access`                  | Synthetic (emitted by `contextToGroups`) | Grants access to all detail views; applied to any user with a `*-detail` Google group                                                                                                                                                                              | Detail vs summary enforcement |
| `summary-access`                 | Synthetic (emitted by `contextToGroups`) | Grants access to all summary views; applied to any user with a `*-detail` or `*-summary` Google group                                                                                                                                                              | Detail vs summary enforcement |
| `cube-access-student-data`       | Google group                             | Required to see any student-domain cube members (attendance, assessment, gradebook, behavioral, surveys, students, student status dims). Enforced solely via `queryRewrite` `isStudentMember` check (`startsWith("student")`); not present in view access policies | Pattern 3                     |
| `cube-access-student-pii`        | Google group                             | Unlocks student direct identifiers (name, DOB, LEA/state/district IDs, Salesforce contact ID, contact name/phone) on detail views                                                                                                                                  | Pattern 1                     |
| `cube-access-staff-pii`          | Google group                             | Unlocks staff direct identifiers and sensitive HR narratives (name, DOB, emails, phone, AD username, employee number, termination reason/date) on detail views                                                                                                     | Pattern 1                     |
| `cube-access-staff-compensation` | Google group                             | Unlocks pay rate fields (annual wage, hourly wage, daily rate, period rate, additional earnings) on staff compensation views                                                                                                                                       | Pattern 2                     |
| `cube-access-staff-benefits`     | Google group                             | Unlocks benefits enrollment fields (plan type, plan name, coverage level) on staff benefits views                                                                                                                                                                  | Pattern 4                     |
| `cube-access-staff-observations` | Google group                             | Unlocks individual observation records, scores, and free-text feedback fields on observations detail views; row-level scoping to own school enforced separately via `queryRewrite`                                                                                 | Pattern 5                     |

### Pattern 1 — PII fields

Present in the detail view field list, hidden from users without the PII group.
Default deny on the specific fields; PII group restores full access.

**Staff PII** — direct identifiers and sensitive HR narratives gated by
`cube-access-staff-pii`. All carry `meta: {pii: true}` on the cube dimension.

```yaml
# applied on detail views that include staff PII
access_policy:
  - group: detail-access
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
  - group: cube-access-staff-pii
    member_level:
      includes: "*"
```

**Student PII** — direct identifiers gated by `cube-access-student-pii`. All
carry `meta: {pii: true}` on the cube dimension.

```yaml
# applied on detail views that include student PII
access_policy:
  - group: detail-access
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
  - group: cube-access-student-pii
    member_level:
      includes: "*"
```

**Sensitive demographics** — `meta: {pii: true}` tagged in the cube but visible
at base access level; not in any `excludes:` list. Included in both detail and
summary views for trend analysis. BI-layer cell suppression applies for small
populations.

- Students: `gender_identity`, `race`, `meal_eligibility`, `is_ell`, `is_iep`,
  `is_gifted`
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
  - group: detail-access
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
  - group: cube-access-staff-compensation
    member_level:
      includes: "*"
```

### Pattern 3 — Student domain visibility

`queryRewrite` in `cube.js` strips all dimensions and measures whose cube name
starts with `student` (via `isStudentMember`) from queries for users without
`cube-access-student-data`. This is the sole enforcement point for student data
access — no separate `cube-access-student-data` block appears in view access
policies.

Student-domain detail views use the same `group: detail-access` gating as all
other detail views (Pattern 1 for PII fields, `detail-access` base block). A
user who has `detail-access` but lacks `cube-access-student-data` can
technically reach the view endpoint, but `queryRewrite` strips all
student-prefixed members and the query returns nothing useful. Student-domain
summary views gate on `group: summary-access` with no additional block.

There is no separate belt-and-suspenders `group: "*"` deny block. The
detail/summary split is the view-level gate; `queryRewrite` is the data-level
gate.

### Pattern 4 — Benefits fields

Applied on the staff benefits view. Benefits enrollment data can reveal health
information — plan type and coverage tier are proxies for health status and
family circumstances. Per ADA, benefits data must be treated separately from
general personnel records. All carry `meta: {pii: true}` on the cube dimension.

Fields: `plan_type`, `plan_name`, `coverage_level` (from `staff_benefits`).

```yaml
access_policy:
  - group: detail-access
    member_level:
      includes: "*"
      excludes:
        - plan_type
        - plan_name
        - coverage_level
  - group: cube-access-staff-benefits
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

**Row-level scoping** (`queryRewrite` in `cube.js`): Row-level location gating
is provided by the existing `queryRewrite` location filter, derived from the
user's Google group — no observations-specific mechanism is needed. A user with
`cube-school-bold-detail` has `locations.abbreviation IN ('bold')` injected on
every query; a regional user gets a `locations.region_key` filter; a network
user gets no location filter. This applies to observations queries the same as
any other domain.

The two layers are independent: a user without `cube-access-staff-observations`
sees nothing regardless of school scope. The location filter only narrows rows
for users who have already passed the column gate.

```yaml
# observations_detail.yml
access_policy:
  - group: detail-access
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
  - group: cube-access-staff-observations
    member_level:
      includes: "*"
```

Row-level school scoping is enforced in `cube.js` via `queryRewrite` — not in
the access policy. The access policy controls column visibility; `queryRewrite`
controls row visibility for users who pass the column gate.

## cube.js Changes

The following changes to `src/cube/cube.js` are required alongside the YAML
implementation. Apply them exactly as shown.

### Replace STUDENT_CUBES / STAFF_CUBES lists with prefix helpers

Remove the static cube name lists and replace with naming-convention-driven
helpers. Add `withSyntheticGroups` for detail/summary view gating.

Replace this block (after `nextMidnightEastern`):

```javascript
// STUDENT_CUBES: cubes that require cube-access-student-data.
// Add cube name: here when adding a new student-data cube.
const STUDENT_CUBES = [
  "attendance",
  "dim_student_ell_status",
  "dim_student_iep_status",
  "dim_student_meal_eligibility_status",
];

const STAFF_CUBES = [
  "dim_staff",
  "fct_staff_attrition",
  "fct_staff_observations",
];
```

With:

```javascript
// Naming convention drives security — no lists to maintain.
// student cubes: name starts with "student" (students, student_attendance, etc.)
// staff cubes:   name starts with "staff"   (staff, staff_attrition, etc.)
// conformed dims: bare business name (dates, locations, regions, terms, school_calendars)
function isStudentMember(m) {
  return m.startsWith("student");
}
function isStaffMember(m) {
  return m.startsWith("staff");
}

// Emit synthetic access groups so view access_policy blocks can gate on
// detail vs summary independently of the specific school/region group.
// These are NOT cached — derived fresh from the cached real groups on each
// contextToGroups call so the cache stays clean for queryRewrite lookups.
//
// Tier is derived from the SAME effective scope group that queryRewrite uses
// (network > region > school). A lower-priority detail group cannot escalate
// access beyond what the effective scope grants.
function withSyntheticGroups(cubeGroups) {
  const result = [...cubeGroups];
  const effectiveScope =
    cubeGroups.find((g) => g.startsWith("cube-network-")) ??
    cubeGroups.find((g) =>
      /^cube-region-[a-z0-9][a-z0-9-]*-(?:detail|summary)$/.test(g),
    ) ??
    cubeGroups.find((g) =>
      /^cube-school-[a-z0-9][a-z0-9-]*-(?:detail|summary)$/.test(g),
    );
  if (effectiveScope?.endsWith("-detail")) result.push("detail-access");
  if (
    effectiveScope?.endsWith("-detail") ||
    effectiveScope?.endsWith("-summary")
  )
    result.push("summary-access");
  return result;
}
```

### Wrap all three `contextToGroups` return sites with `withSyntheticGroups`

Three places return groups — each needs the wrapper:

```javascript
// CUBE_GROUP_MAP branch (local dev)
return withSyntheticGroups(groups);

// Cache hit branch
return withSyntheticGroups(cached.groups);

// API branch (after storing to cache)
return withSyntheticGroups(cubeGroups);
```

### Update `queryRewrite` to use helpers instead of list iteration

Replace:

```javascript
dimensions: (query.dimensions ?? []).filter(
  (d) => !STUDENT_CUBES.some((c) => d.startsWith(c)),
),
measures: (query.measures ?? []).filter(
  (m) => !STUDENT_CUBES.some((c) => m.startsWith(c)),
),
```

With:

```javascript
dimensions: (query.dimensions ?? []).filter((d) => !isStudentMember(d)),
measures: (query.measures ?? []).filter((m) => !isStudentMember(m)),
```

And replace:

```javascript
].some((m) => STAFF_CUBES.some((c) => m.startsWith(c)));
```

With:

```javascript
].some((m) => isStaffMember(m));
```

### Update location filter member references

Three `member:` strings in `queryRewrite` reference the old `dim_` cube names.
Update each to the unprefixed cube name:

```javascript
// region filter
member: "locations.region_key",

// school filter
member: "locations.abbreviation",

// default-deny filter
member: "locations.abbreviation",
```

### Update `reporting_chain` segment reference

```javascript
segments: [...(query.segments ?? []), "staff.reporting_chain"],
```
