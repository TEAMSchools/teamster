# Cube Connector Gap Catalog

Refs [#5673](https://github.com/TEAMSchools/teamster/issues/5673). Design:
[2026-10-02-cube-connector-gap-catalog-design.md](../specs/2026-10-02-cube-connector-gap-catalog-design.md).

A priority-agnostic catalog of every measure and dimension displayed on the
core-set Tableau dashboards, classified against the dbt marts
(`src/dbt/kipptaf/models/marts/`) and the Cube model YAML (`src/cube/model/`),
with per-gap regional coverage and a reconciliation against the Asana "Data
Marts + Semantic Layer" project. No sequencing or milestones — sequencing is a
later pass.

## Scope and method

The core set is every `docs/launch/links.yml` entry with `system: tableau` and
`status: verified`: **31 dashboards** (the design spec said 30; the recount
during extraction found 31). For each one, the production workbook was
downloaded from the KIPPNJ Tableau site and its XML parsed. Inventory grain:
every measure on a sheet that appears on a published dashboard (hidden scratch
sheets and pure formatting calcs excluded; tooltip-only measures flagged), plus
every dimension used to slice, filter, or color those measures. Published status
was verified against the server's own view list, not just the workbook file —
several workbooks carry archived or orphaned dashboards that are not live.

Each row carries one status:

| Status          | Meaning                                                 |
| --------------- | ------------------------------------------------------- |
| `cube-covered`  | A Cube measure/dimension exists in `src/cube/model/`    |
| `mart-ready`    | A `fct_`/`dim_` column carries it; no Cube measure yet  |
| `mart-missing`  | No mart carries it; the `rpt_` model holds the logic    |
| `workbook-only` | Tableau-side calc not worth porting; flagged, not built |

Detail lives in the per-domain files, one section per dashboard:

- [Attendance](2026-10-02-cube-gap-catalog-attendance.md)
- [Students](2026-10-02-cube-gap-catalog-students.md)
- [Assessments](2026-10-02-cube-gap-catalog-assessments.md)
- [Behavior](2026-10-02-cube-gap-catalog-behavior.md)
- [Grades](2026-10-02-cube-gap-catalog-grades.md)
- [Postsecondary](2026-10-02-cube-gap-catalog-postsecondary.md)
- [Staff](2026-10-02-cube-gap-catalog-staff.md)
- [Observations](2026-10-02-cube-gap-catalog-observations.md)
- [Surveys](2026-10-02-cube-gap-catalog-surveys.md)
- [Talent](2026-10-02-cube-gap-catalog-talent.md)
- [Support](2026-10-02-cube-gap-catalog-support.md)
- [Student Recruitment](2026-10-02-cube-gap-catalog-student-recruitment.md)
- [Stipends and Certification](2026-10-02-cube-gap-catalog-stipends-cert.md)

## Headline

Across the 31 dashboards, roughly 383 grouped measure rows (each row often
collapses many per-subject or per-term Tableau calc variants) and 546 grouped
dimension rows were classified:

| Status          | Measures   | Dimensions |
| --------------- | ---------- | ---------- |
| `cube-covered`  | ~59 (15%)  | ~194 (36%) |
| `mart-ready`    | ~142 (37%) | ~172 (31%) |
| `mart-missing`  | ~146 (38%) | ~143 (26%) |
| `workbook-only` | ~36 (9%)   | ~35 (6%)   |

Counts are computed from each row's primary status; rows with split or uncertain
status carry caveats in the domain files, which are authoritative. The practical
read: Cube today covers attendance, enrollment, staff directory, and
enrollment-scoped assessment scores well; everything else is either a
Cube-wiring gap over existing marts (observations, surveys, recruiting, support,
parts of staff) or a true modeling gap (postsecondary, behavior points,
grades/GPA goals, FRESH, certification, growth metrics).

## Per-dashboard coverage

Measures and dimensions as `cube-covered/mart-ready/mart-missing/workbook-only`
(`+n` = unclassified/unknown rows):

| Domain        | Dashboard                         | Measures     | Dimensions   |
| ------------- | --------------------------------- | ------------ | ------------ |
| attendance    | `attendance_dashboard`            | 9/5/4/2      | 11/8/1/0     |
| students      | `ops_dashboard`                   | 6/0/10/1     | 12/2/8/1     |
| students      | `data_quality_dashboard`          | 2/4/7/2      | 8/1/3/0      |
| students      | `high_school_early_warning`       | 1/6/8/0      | 10/5/7/0     |
| students      | `promotional_status_dashboard`    | 5/3/6/1 (+1) | 8/3/2/0      |
| assessments   | `carat`                           | 0/10/6/0(+1) | 0/11/4/0(+2) |
| assessments   | `ddi_suite`                       | 11/2/5/5     | 13/1/4/2     |
| assessments   | `fast_and_iready_data_tool`       | 7/0/9/1      | 9/0/8/2      |
| assessments   | `i_ready_apm_tool`                | 5/9/0/0      | 10/9/0/1     |
| assessments   | `lit_dashboard`                   | 1/11/0/1     | 7/10/0/0     |
| assessments   | `state_testing_analysis_tool`     | 4/4/6/4      | 11/6/8/0     |
| assessments   | `testing_accommodations`          | 2/0/4/0      | 9/0/4/2      |
| behavior      | `okrts_dashboard`                 | 0/7/12/2     | 7/6/6/1      |
| grades        | `academic_gradebook_health_suite` | 0/8/12/1     | 0/6/3/1      |
| postsecondary | `kipp_forward_data_suite`         | 0/1/11/1     | 1/2/9/1      |
| staff         | `staff_roster`                    | 2/1/1/1      | 17/0/9/3     |
| staff         | `staff_attrition_dashboard`       | 0/5/2/0 (+1) | 8/4/1/5      |
| staff         | `staff_demographic_explorer`      | 2/0/0/1      | 9/1/4/0      |
| staff         | `finance_and_accounting_tools`    | 2/4/4/3      | 14/7/0/2     |
| observations  | `grow_dashboard`                  | 0/15/4/1     | 0/15/4/0     |
| observations  | `coaching_conversation_tool`      | 0/4/4/1      | 0/13/0/3     |
| observations  | `teacher_development_dashboard`   | 0/8/1/0      | 0/13/2/3     |
| observations  | `leader_pm_dashboard`             | 0/0/3/0      | 8/0/6/2      |
| surveys       | `survey_dashboard`                | 0/13/1/3     | 0/11/3/1     |
| surveys       | `survey_hq`                       | 0/1/0/1      | 0/9/0/1      |
| surveys       | `manager_survey_report`           | 0/3/0/0      | 6/4/1/0      |
| talent        | `recruitment_dashboard`           | 0/11/3/0     | 0/13/5/1     |
| support       | `zendesk_dashboard`               | 0/4/0/1      | 0/9/8/2      |
| student-recr. | `fresh_dashboard`                 | 0/0/9/3      | 3/0/15/0     |
| stipends-cert | `certification_dashboard`         | 0/2/8/0      | 9/2/11/1     |
| stipends-cert | `stipend_and_bonus_dashboard`     | 0/1/6/0      | 4/1/7/0      |

## Cross-cutting findings

### Marts that exist but nothing in Cube reads

The cheapest wins in the catalog are wiring gaps, not modeling gaps:

- `fct_assessment_scores_student_scoped` — SAT/ACT/PSAT/AP at the right grain
  with mastery cutoffs already computed; zero cubes read it. Blocks all of
  CARAT's core metrics.
- Observations family (`fct_staff_observations`, `fct_staff_observation_scores`,
  `fct_staff_observation_goals`, `dim_staff_observation_*`) — covers most of
  Grow, Coaching Conversation Tool, and Teacher Development.
- New dimensional survey family (`fct_survey_responses`,
  `fct_survey_submissions`, `dim_surveys`, `dim_survey_questions`,
  `bridge_survey_*`) — each model's own YAML notes nothing reads it; it already
  ingests manager-survey data.
- Recruiting family (`fct_job_candidate_applications`, `dim_job_candidates`,
  `dim_job_postings`, `dim_staffing_positions`) — covers most of the Recruitment
  Dashboard, including the open `talent.pct_staffed` measure.
- `fct_support_tickets` (Zendesk), `fct_staff_attrition`,
  `fct_work_assignment_compensation` / `_additional_earnings`,
  `fct_staff_benefits_enrollments`.
- `dim_assessment_goals` is declared in `cube.yml` `depends_on` but no cube file
  reads it.

### True modeling gaps (no mart anywhere)

- Postsecondary/alumni: ~85% of the KIPP Forward Data Suite (advising
  touchpoints, application/acceptance/matriculation, ECC grad-rate methodology,
  financial aid, career survey, re-enrollment). The structural missing piece is
  a `dim_alumni` bridging Salesforce contacts to `dim_students`.
- Behavior: the DeansList PBIS point-log feed (OKRTS "Behavior Count" /
  incentive metrics) has no mart; restraint fields never made it into
  `fct_behavioral_consequences` (blocks CRDC restraint metrics).
- Grades: GPA goal targets (`int_gpa__*` only) — exactly the two open Asana
  grade measures; on-track composite logic for HS Early Warning lives only in
  Tableau LODs.
- Enrollment targets / anchor metrics (Ops, FRESH): `fct_anchor_metrics` and
  `fct_enrollment` are named as Asana blockers and genuinely do not exist; FRESH
  is almost entirely mart-missing (Finalsite scaffolds are `int_`-layer only).
- Attendance interventions and the attendance comm log (two of the three
  Attendance Dashboard sources) have zero Cube-domain coverage.
- Growth concepts: no SGP/gain/stretch-growth anywhere in Cube (FLDOE growth,
  iReady gain, STAR SGP); no domain/standard-mastery grain for vendor
  assessments.
- DIBELS beyond Benchmark: PM rounds, aimlines, goals, participation, and sight
  words are structurally absent — the scores fact carries only scored rows, so
  completion/participation cannot be derived for DIBELS the way `pct_taken`
  works for Illuminate.
- Certification: the dashboard's cert content is a hand-maintained Google Sheet
  pulled into Tableau outside dbt/Dagster entirely; an orphaned
  `int_people__certification` model exists with zero consumers.
- 504 status: no `dim_student_504_status` exists (IEP/ELL/meal eligibility each
  have one); `is_504` lives only in intermediates. Recurs on Testing
  Accommodations, Attendance, Promotional Status, and STAT.

### Semantic mismatches to resolve before "cube-covered" is trusted

- Chronic-absence thresholds: the Attendance and HS Early Warning workbooks
  recompute flat `ada <= 0.90` in Tableau; Cube's `is_chronically_absent` / tier
  logic uses the 80/90 tier boundaries. One "chronic tardy" threshold
  (`< 0.795`) matches no documented rule.
- DIBELS mastery: Cube's `is_mastery` (per-measure standard level) is not the
  dashboards' composite At/Above rate.
- `performance_band_label_number` is null for state and vendor rows in
  `fct_assessment_scores_enrollment_scoped`, blocking band ordering/bucketing
  (STAT Below/Far Below, FAST sublevels, STAR/iReady level sort).
- Tableau parameter-swap fields (Attendance Metric, STAT Comps Selector, survey
  Cut-By) have no single-Cube-member equivalent; each needs N measures plus a
  client-side switch.
- Rolling windows and ranks: Miami's 15-absences-in-90-days truancy LOD and the
  MTSS percentile-rank eligibility (`percent_rank()` per school/grade) are not
  expressible in the current Cube design.
- Row-level security: Tableau `ISMEMBEROF()` gates (surveys, stipends, staff,
  teacher development) need a deliberate mapping onto Cube `access_policy`
  remits. One inversion to decide: Staff Demographic Explorer is open in Tableau
  today, but its demographic fields sit behind Cube's `staff_pii` remit.

### Regional coverage notes

Regional scope is per-dashboard data, recorded on every row in the domain files.
The non-uniform cases found:

| Dashboard / surface                   | Actual regional scope            |
| ------------------------------------- | -------------------------------- |
| Attendance Dashboard (all tabs but 1) | Camden/Newark/Paterson (hard)    |
| Attendance "Miami - NSLP" tab         | Miami only (own truancy logic)   |
| Promotional Status (both dashboards)  | Newark/Camden/Miami; no Paterson |
| Testing Accommodations                | Newark/Camden only (SQL WHERE)   |
| Gradebook audit sheets                | Excludes Miami and ES            |
| CARAT AP/DE Overview                  | PowerSchool regions only (NJ)    |
| FAST & iReady Data Tool               | Miami only (SQL WHERE)           |
| Sight Words (LIT)                     | Newark/Camden                    |
| HS Early Warning grad requirements    | Excludes Miami                   |
| Teacher Development                   | Newark/Camden/Miami; no Paterson |
| Recruitment Dashboard                 | Newark/Camden/Miami visible only |
| DDI differentiated goals              | NJ regions only; Miami bare goal |

Everything else verified network-wide (often with viewer-level RLS, which is not
a data restriction).

### Candidates to descope or confirm

- Leader PM Dashboard: its only source model
  (`rpt_tableau__leadership_development`) is `enabled: false` — Leadership
  Development moved to Lattice (#4627). Confirm before scoping any build.
- Several workbooks carry archived/orphaned dashboards not published on the
  server (Attendance x4, Ops x1, iReady APM x2, Staff Roster x5, Stipend x2,
  Staff Attrition x2, Data Quality x3, Leadership x2). Each domain file lists
  them; they are excluded from counts.
- Non-Production project locations worth confirming: Staff Demographic Explorer
  publishes from "The Brass", Finance & Accounting Tools from "TEMP-KV".

## Asana reconciliation (report-only)

Project: Data Marts + Semantic Layer (Asana gid 1213735218595734).

### Core-set dashboards with no Asana task

- Leader PM Dashboard (also a descope candidate, above)
- Manager Survey Report (~12.7k historical views on its one view)

### Tasks with empty notes (no workbook LSID, no rpt_ list)

Staff Roster, Staff Demographic Explorer, Attrition Dashboard, Finance Tools.
The domain files record the real luid and rpt_ models for each, ready to
backfill.

### Task metadata that does not match the live workbook

- Gradebook and GPA Dashboard: stale LSID (live workbook is a different luid at
  `AcademicGradebookHealthSuite`) and a stale rpt_ list — only
  `rpt_tableau__gradebook_audit` of its five named models is actually read; the
  live workbook reads `rpt_tableau__student_course_grades`,
  `rpt_tableau__gpa_cumulative_year`, `rpt_tableau__gpa_goals`,
  `rpt_tableau__gpa_goal_progress` instead.
- NJ Certification Dashboard: claims `rpt_tableau__staff_roster` (a shared HR
  extract that supplies zero cert content); the cert content itself comes from a
  Google Sheet outside dbt.
- KIPP Forward Data Suite: list omits `rpt_tableau__kfwd_aid_report` and
  `rpt_gsheets__kfwd_rem_roster`, both live datasources.
- Recruitment Dashboard: names `rpt_tableau__seat_tracker`, but only the
  `_snapshot` variant is a datasource; the Interview/Demo Tracking dashboard
  reads a non-warehouse calendar extract with no dbt model.
- High School Early Warning: names `rpt_tableau__grad_plan_tracking`, which does
  not exist (real model `rpt_gsheets__grad_plan_tracking` is not a datasource of
  this workbook).
- Survey HQ / Personalized Survey Links: the embedded datasource caption says
  `survey_completion` but the actual relation is `rpt_tableau__survey_links`.
- Zendesk Reporting: blocker `fct_tableau_usage` appears to be a typo for
  `fct_support_tickets` (which exists).

### Stale blocker names (pattern across many tasks)

Task blockers predate the shipped marts and use planned names:
`fct_observations` → `fct_staff_observations`; `fct_incidents`/`fct_behaviors` →
`fct_behavioral_incidents`/`fct_behavioral_consequences`; `fct_course_grades` →
`fct_grades_term`/`fct_grades_gpa`; `dim_observation_rubrics` →
`dim_staff_observation_rubrics`; and `dim_students`/`dim_locations`/`dim_terms`
exist despite being listed as blockers. Conversely `fct_anchor_metrics`,
`fct_enrollment`, `fct_state_assessments`, `fct_iready_diagnostics`,
`fct_postsecondary_*`, `fct_stipends`, and `fct_staff_seats` genuinely do not
exist.

### Asana tasks for dashboards outside the core set

Newark Home Instruction Tracker and Miami Instructional Rubrics (= the launch
page's `content_team`, status `needs-review`) have per-dashboard Asana tasks but
are not in the verified core set; the OKRTS workbook also carries its own Home
Instruction dashboard backed by `rpt_tableau__home_instruction`.

## Known limits of this pass

- Classification is from workbook XML plus repo reads; no live Cube `meta` calls
  or warehouse row counts were used. Rows the extractors could not settle are
  flagged `unknown`/caveated in the domain files rather than guessed.
- Tableau-native "(group)" bins store no formula in the XML (notably on the
  Staff Attrition dashboard); their bucketing rules need the live workbook or
  Desktop to reverse-engineer.
- Counts in this index are mechanical tallies of each row's primary status;
  split rows are counted once.
