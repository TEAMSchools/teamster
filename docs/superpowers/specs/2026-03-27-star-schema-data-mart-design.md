# Star Schema Data Mart Design

## Summary

A conformed star schema data mart for the kipptaf dbt project, designed to be
mapped onto a Cube semantic layer and consumed by all reporting. This mart
replaces the role of the existing `models/extracts/` folder over time — Cube
handles analytics consumers (Tableau, Google Sheets, DeansList, ad-hoc), while
thin dbt extract models on top of the mart handle system integration feeds
(Clever, PowerSchool autocomm, ADP, IDauto, etc.) where format requirements
don't belong in a semantic layer. Dagster assets query the mart/Cube and deliver
files to target systems.

## Scope

- Design and build the complete star schema in `models/marts/` with
  `dimensions/`, `facts/`, and `bridges/` subdirectories.
- Does NOT include: Cube semantic layer configuration, rewiring existing
  extracts, or retiring existing models. Those are future projects that consume
  this deliverable.

## Architectural Decisions

| Decision                 | Choice                                                                                                                           | Rationale                                                                                                             |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Multi-region handling    | `dim_regions` as its own normalized dimension                                                                                    | Clean FK on all facts; supports region-specific logic in Cube                                                         |
| Business logic split     | Balanced — dbt handles structural logic and stable business rules; Cube handles presentation logic and consumer-specific shaping | Pragmatic boundary between warehouse and semantic layer                                                               |
| System integration feeds | Thin dbt extracts on top of mart + Dagster for delivery                                                                          | Cube stays purely analytical; format-specific shaping doesn't belong in semantic layer                                |
| Time/calendar            | Role-playing `dim_dates` + `dim_terms`                                                                                           | Ad-hoc date filtering is a primary concern; every meaningful date on a fact gets a first-class dimension relationship |
| `dim_terms` scope        | Generalized beyond academic terms                                                                                                | Covers academic terms, performance management rounds, survey windows, assessment admin windows, fiscal periods        |
| SCDs                     | Hybrid — Type 2 where history matters (staff, enrollments), Type 1 for stable/static dims                                        | Keeps complexity where it adds value                                                                                  |
| Assessment facts         | Single unified `fct_assessment_scores` with nullable columns for assessment-family-specific fields                               | Simpler cross-assessment analysis; Cube handles conditional column exposure                                           |
| Gradebook facts          | Full hierarchy — term grades, category grades, assignments                                                                       | Assignments are important even though current extract usage is limited                                                |
| GPA                      | Pre-calculated `fct_gpa` fact                                                                                                    | Cumulative/weighted/unweighted logic too complex for Cube calculation                                                 |
| Attendance               | Separate facts by business process                                                                                               | Daily attendance, interventions, and communications have different grains                                             |
| People domain            | Normalized — person, work assignment, compensation, reporting relationship as separate dims                                      | Different change cadences; manager and comp can change within same assignment                                         |
| Course domain            | Normalized — course catalog separate from sections                                                                               | Clean separation of catalog vs instance                                                                               |
| Mart directory structure | `marts/dimensions/`, `marts/facts/`, `marts/bridges/`                                                                            | Mirrors how Cube thinks; star schema role is the organizing principle                                                 |
| Build order              | Conformed dimensions first, then domain facts                                                                                    | Facts depend on conformed dims; clear dependency ordering                                                             |

## Model Inventory

### Conformed Dimensions

| Model           | SCD    | Grain                                                                                         | Key Sources                                                                                                                 |
| --------------- | ------ | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `dim_dates`     | Static | one row per calendar date (2000-01-01 to 2050-12-31)                                          | Generated — day of week, month, quarter, year, is_weekday, academic_year, fiscal_year                                       |
| `dim_terms`     | Type 1 | one row per named period x region (region nullable for org-wide periods like fiscal quarters) | Google Sheets reporting terms, performance management rounds, survey windows, assessment admin windows, fiscal periods      |
| `dim_regions`   | Type 1 | one row per region                                                                            | Newark, Camden, Miami, Paterson — state, timezone, regulatory context                                                       |
| `dim_locations` | Type 1 | one row per school/office                                                                     | `int_people__location_crosswalk` — region, grade band, campus, school IDs (PowerSchool, DeansList, reporting), abbreviation |

### Student Domain

| Model                     | SCD    | Grain                                                            | Key Sources                                                                                                                                |
| ------------------------- | ------ | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `dim_students`            | Type 1 | one row per student                                              | PowerSchool — student_number, SSID, FLEID, name, birth_date, gender, race/ethnicity, is_gifted, has_iep, is_ell, lunch_status              |
| `dim_student_enrollments` | Type 2 | student x school x year (effective dates for mid-year transfers) | `int_extracts__student_enrollments`, PowerSchool enrollments — grade_level, graduation_year, school_level, enroll_status, is_retained_year |
| `dim_student_contacts`    | Type 1 | student x contact person                                         | PowerSchool student contacts — contact_name, relationship, phone, email, is_emergency, is_primary, contact_priority                        |

**Foreign keys on `dim_student_enrollments`:**

- `student_key` -> `dim_students`
- `location_key` -> `dim_locations`
- `region_key` -> `dim_regions`
- `entry_date_key` -> `dim_dates` (role-playing)
- `exit_date_key` -> `dim_dates` (role-playing)

### Staff Domain

| Model                         | SCD    | Grain                        | Key Sources                                                                                                                                                                      |
| ----------------------------- | ------ | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_people`                  | Type 2 | one row per person x version | ADP workers, LDAP, surveys — name, birth_date, gender, race/ethnicity, education, alumni_status, contact info (personal/work email, phone, address), LDAP/Google/UPN identifiers |
| `dim_work_assignments`        | Type 2 | person x position x version  | ADP work assignments — job_title, department, assignment_status, worker_type, management_indicator, benefits_eligibility, payroll_group                                          |
| `dim_compensation`            | Type 2 | person x position x version  | ADP — base_annual_rate, hourly_rate, additional_remunerations, wage_law                                                                                                          |
| `dim_reporting_relationships` | Type 2 | person x version             | ADP + leadership crosswalk — reports_to_employee_number, reports_to_name, reports_to_email                                                                                       |

**Foreign keys on `dim_work_assignments`:**

- `person_key` -> `dim_people`
- `location_key` -> `dim_locations`
- `compensation_key` -> `dim_compensation`
- `reporting_relationship_key` -> `dim_reporting_relationships`
- `effective_date_start_key` -> `dim_dates` (role-playing)
- `effective_date_end_key` -> `dim_dates` (role-playing)

**Primary upstream source:** `int_people__staff_roster_history` — the mart
decomposes this 223-column denormalized model back into normalized dimensions.
Column-level mapping during implementation may reveal additional splits.

### Course Domain

| Model          | SCD    | Grain                         | Key Sources                                                                                               |
| -------------- | ------ | ----------------------------- | --------------------------------------------------------------------------------------------------------- |
| `dim_courses`  | Type 1 | one row per course in catalog | PowerSchool courses — course_number, course_name, discipline, credit_hours                                |
| `dim_sections` | Type 1 | one row per section x term    | PowerSchool sections — section_number, teacher (FK -> `dim_people`), location_key, term_key, period, room |

### Assessment Domain

| Model             | SCD    | Grain                             | Key Sources                                                                                                                                                  |
| ----------------- | ------ | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `dim_assessments` | Type 1 | one row per assessment definition | Assessment metadata — assessment_type (SAT, PSAT, AP, iReady, STAR, DIBELS, FAST, NJSLA, internal), subject, scope, grade_level_tested, benchmark thresholds |

### College Domain

| Model          | SCD    | Grain                   | Key Sources                                            |
| -------------- | ------ | ----------------------- | ------------------------------------------------------ |
| `dim_colleges` | Type 1 | one row per institution | NSC — college_name, type (2yr/4yr), selectivity, state |

### Facts

| Model                                     | Grain                                 | Key Foreign Keys                                                                                                                              | Key Measures                                                                                                                                                                        |
| ----------------------------------------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fct_term_grades`                         | student x course x term               | student_key, section_key, term_key, region_key, date_key (role-playing)                                                                       | percent_grade, letter_grade, citizenship_grade                                                                                                                                      |
| `fct_category_grades`                     | student x course x term x category    | student_key, section_key, term_key, region_key                                                                                                | category_name, category_weight, percent_grade                                                                                                                                       |
| `fct_assignments`                         | student x assignment                  | student_key, section_key, term_key, region_key, due_date_key (role-playing)                                                                   | assignment_name, score, points_possible, is_missing, is_late, category                                                                                                              |
| `fct_gpa`                                 | student x term                        | student_key, term_key, region_key, location_key                                                                                               | cumulative_gpa, term_gpa, weighted/unweighted variants, credit_hours_earned, credit_hours_attempted                                                                                 |
| `fct_assessment_scores`                   | student x assessment x administration | student_key, assessment_key, test_date_key (role-playing), term_key, region_key, location_key                                                 | scale_score, percent_correct, proficiency_level, achievement_level, growth_percentile, section_scores (nullable), superscore (nullable), college_readiness_benchmark_met (nullable) |
| `fct_attendance`                          | student x date                        | student_key, date_key, location_key, region_key, term_key                                                                                     | attendance_code, excused/unexcused, present/absent/tardy/early_dismissal                                                                                                            |
| `fct_attendance_interventions`            | student x intervention event          | student_key, staff_key (-> dim_people), intervention_date_key (role-playing), location_key, region_key                                        | intervention_type, outcome                                                                                                                                                          |
| `fct_attendance_communications`           | student x communication event         | student_key, staff_key (-> dim_people), communication_date_key (role-playing), location_key, region_key                                       | communication_method, outcome                                                                                                                                                       |
| `fct_staff_attrition`                     | person x termination event            | person_key, work_assignment_key, termination_date_key (role-playing), region_key, location_key                                                | termination_reason, voluntary/involuntary                                                                                                                                           |
| `fct_performance_management_observations` | person x observation event            | person_key, work_assignment_key, observer_key (-> dim_people), observation_date_key (role-playing), term_key, region_key, location_key        | rubric_score, measurement_name, strand                                                                                                                                              |
| `fct_behavioral_incidents`                | student x incident                    | student_key, referring_staff_key (-> dim_people), incident_date_key (role-playing), location_key, region_key                                  | incident_type                                                                                                                                                                       |
| `fct_behavioral_consequences`             | student x incident x consequence      | student_key, incident_key (-> fct_behavioral_incidents), start_date_key (role-playing), end_date_key (role-playing), location_key, region_key | consequence_type, duration, is_served                                                                                                                                               |
| `fct_college_enrollments`                 | student x college x term              | student_key, college_key (-> dim_colleges), enrollment_date_key (role-playing), region_key                                                    | enrollment_status, degree_pursued                                                                                                                                                   |

**Total: 15 dimensions + 13 facts = 28 models**

## Role-Playing Date Keys

Every fact carries one or more foreign keys to `dim_dates`. Each key represents
a different date role. In Cube, each role-playing key is defined as a separate
join to `dim_dates` with an alias, enabling full drill/filter/group capability
on any date role.

Examples:

- `fct_attendance`: `date_key`
- `fct_staff_attrition`: `termination_date_key`
- `fct_behavioral_consequences`: `start_date_key`, `end_date_key`
- `dim_student_enrollments`: `entry_date_key`, `exit_date_key`

## Slowly Changing Dimension Strategy

| SCD Type                | Applied To                                                                                                                                                         | Behavior                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| Type 1 (overwrite)      | `dim_students`, `dim_student_contacts`, `dim_regions`, `dim_locations`, `dim_courses`, `dim_sections`, `dim_assessments`, `dim_colleges`, `dim_terms`, `dim_dates` | Current state only; corrections overwrite                                                                                    |
| Type 2 (versioned rows) | `dim_people`, `dim_work_assignments`, `dim_compensation`, `dim_reporting_relationships`, `dim_student_enrollments`                                                 | Versioned with `effective_date_start`, `effective_date_end`, `is_current_record`; facts link to version active at event time |

## Open Review Items

The following items need validation before or during implementation:

### 1. Student-to-Section Enrollment Fact

We have `dim_sections` and gradebook facts, but no explicit
`fct_student_course_enrollments`. A student being enrolled in a section is a
distinct event from having a grade. The old marts had this model. Needed for
roster counts, section utilization, and roster-based system feeds (Clever,
etc.).

**Decision needed:** Include as a separate fact or derive from gradebook facts?

### 2. Bridge Tables

The `marts/bridges/` subdirectory exists in the design but no bridge tables have
been identified. Candidates for multi-valued dimension relationships:

- Students with multiple race/ethnicity codes
- Staff with multiple group memberships (ADP memberships)
- Students with multiple special program flags

**Decision needed:** Which multi-valued relationships require bridge tables?

### 3. Old Mart Models Not Yet Mapped

The following models exist in the current `models/marts/` and were not carried
forward. Review whether they should be included:

- `fct_additional_earnings` — staff supplemental pay
- `fct_staff_benefits_enrollments` — pension/benefits enrollment
- `fct_microgoals` — unclear domain, needs investigation
- `dim_seats` — staffing model from AppSheet seat tracker
- `dim_state_assessment_benchmarks` / `dim_assessment_goals` — may fold into
  `dim_assessments` or warrant separate dimensions

### 4. Staff Headcount / Periodic Snapshot

The design uses Type 2 SCDs for staff dimensions, which supports point-in-time
queries. However, trend analysis ("headcount by month", "FTE by quarter")
typically requires either:

- A periodic snapshot fact (`fct_staff_snapshot` at monthly or yearly grain)
- Cube doing point-in-time queries against the Type 2 SCD

**Decision needed:** Validate that Cube can efficiently query Type 2 SCDs for
trend analysis, or add a periodic snapshot fact.

### 5. Chronic Absenteeism Streaks in Cube

The design assumes Cube can calculate chronic absenteeism rates via ad-hoc date
range filtering over `fct_attendance`. This works for rate calculations
(`absent_days / total_membership_days`). However, **streak calculations**
(consecutive absences) require ordered window functions that may not map cleanly
to Cube measures.

**Decision needed:** Validate Cube's ability to handle streak calculations, or
add pre-calculated streak columns to `fct_attendance`.

### 6. Behavioral Domain Relationships

The design models `fct_behavioral_incidents` and `fct_behavioral_consequences`
as a parent-child fact relationship (consequences carry `incident_key` FK). This
assumes one incident can have multiple consequences.

**Decision needed:** Confirm with a domain expert that this accurately
represents the DeansList data model and business process.

### 7. College/Post-Secondary Domain

The design includes `dim_colleges` and `fct_college_enrollments` based on NSC
data and the KIPP Forward program extracts.

**Decision needed:** Confirm with a domain expert that this captures the full
scope of post-secondary tracking needs (matriculation, persistence, degree
completion, career outcomes).

### 8. Staff Domain Decomposition

The people/staff dimension split (`dim_people`, `dim_work_assignments`,
`dim_compensation`, `dim_reporting_relationships`) was designed based on change
cadence analysis of `int_people__staff_roster_history`. The 223-column source
model is complex.

**Decision needed:** Column-level mapping during implementation may reveal
additional decomposition needs. Flag for detailed review when building these
models.

## Conventions

All models follow existing dbt project conventions documented in
`src/dbt/CLAUDE.md` and `src/dbt/kipptaf/CLAUDE.md`:

- `contract: enforced: true` (inherited from `dbt_project.yml` directory config)
- Uniqueness tests on all models
- No `SELECT *` in final SELECT of mart models
- Column ordering per ST06 rule
- `current_date('{{ var("local_timezone") }}')` for timezone-aware dates
- `union_dataset_join_clause()` macro for cross-region joins
- Surrogate keys via `dbt_utils.generate_surrogate_key()`
