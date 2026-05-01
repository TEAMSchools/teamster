# Mart YAML Audit Report — 2026-05-01

Run: 17dd1704f | Models scanned: 70 | Pass: 67 | Suspect: 1 | Broken: 2 |
Warn-masked: 0 | Status-mismatch: 2 | Type drift: 0 | Missing-test: 0

## Summary table

| Model                                            | Materialization | Contract | Type drift | Grain status | Test severity | Dagster status | BQ probe  | Difficulty | Disposition | Issue |
| ------------------------------------------------ | --------------- | -------- | ---------- | ------------ | ------------- | -------------- | --------- | ---------- | ----------- | ----- |
| bridge_assessment_expectations_enrollment_scoped | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| bridge_assessment_expectations_student_scoped    | view            | enforced | 0          | pass         | error         | WARN           | unique    | TBD        | TBD         | —     |
| bridge_course_section_teachers                   | view            | enforced | 0          | suspect      | error         | PASSED         | over-spec | TBD        | TBD         | —     |
| bridge_course_section_terms                      | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| bridge_student_contacts                          | view            | enforced | 0          | pass         | error         | WARN           | unique    | TBD        | TBD         | —     |
| bridge_survey_expectations                       | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| bridge_survey_questions                          | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_assessment_administrations                   | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_assessment_comparisons                       | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_assessment_goals                             | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_assessments                                  | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_college_enrollments                          | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_colleges                                     | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_course_sections                              | view            | enforced | 0          | pass         | error         | WARN           | unique    | TBD        | TBD         | —     |
| dim_courses                                      | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_dates                                        | table           | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_job_candidates                               | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_job_postings                                 | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_locations                                    | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_regions                                      | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_school_calendars                             | view            | enforced | 0          | pass         | error         | WARN           | unique    | TBD        | TBD         | —     |
| dim_staff                                        | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_staff_observation_expectations               | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_staff_observation_goal_types                 | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_staff_observation_rubric_measurements        | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_staff_observation_rubrics                    | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_staff_observation_types                      | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_staff_status                                 | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_staff_work_assignments                       | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_staffing_positions                           | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_student_attendance_intervention_types        | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_student_contact_persons                      | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_student_enrollments                          | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_student_section_enrollments                  | view            | enforced | 0          | pass         | error         | WARN           | unique    | TBD        | TBD         | —     |
| dim_students                                     | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_survey_administrations                       | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_survey_questions                             | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_surveys                                      | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_terms                                        | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_work_assignment_jobs                         | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_work_assignment_locations                    | view            | enforced | 0          | pass         | error         | WARN           | unique    | TBD        | TBD         | —     |
| dim_work_assignment_organizational_units         | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_work_assignment_primary                      | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_work_assignment_reporting_relationships      | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_work_assignment_status                       | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| dim_work_assignment_types                        | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_assessment_scores_enrollment_scoped          | view            | enforced | 0          | pass         | error         | WARN           | unique    | TBD        | TBD         | —     |
| fct_assessment_scores_student_scoped             | view            | enforced | 0          | pass         | error         | WARN           | unique    | TBD        | TBD         | —     |
| fct_behavioral_consequences                      | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_behavioral_incidents                         | view            | enforced | 0          | pass         | error         | WARN           | unique    | TBD        | TBD         | —     |
| fct_family_communications                        | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_grades_assignments                           | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_grades_category                              | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_grades_gpa                                   | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_grades_term                                  | view            | enforced | 0          | pass         | error         | WARN           | unique    | TBD        | TBD         | —     |
| fct_job_candidate_applications                   | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_staff_attrition                              | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_staff_benefits_enrollments                   | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_staff_membership_enrollments                 | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_staff_observation_goals                      | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_staff_observation_scores                     | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_staff_observations                           | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_student_attendance_daily                     | view            | enforced | 0          | pass         | error         | WARN           | unique    | TBD        | TBD         | —     |
| fct_student_attendance_interventions             | view            | enforced | 0          | broken       | error         | WARN           | dupes     | TBD        | TBD         | —     |
| fct_student_attendance_streaks                   | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_support_tickets                              | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_survey_responses                             | view            | enforced | 0          | broken       | error         | WARN           | dupes     | TBD        | TBD         | —     |
| fct_survey_submissions                           | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_work_assignment_additional_earnings          | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |
| fct_work_assignment_compensation                 | view            | enforced | 0          | pass         | error         | PASSED         | unique    | TBD        | TBD         | —     |

## Per-model details

### bridge_assessment_expectations_enrollment_scoped

- Test severity: error
- Dagster current status: PASSED (1777587775.6052377)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### bridge_assessment_expectations_student_scoped

- Test severity: error
- Dagster current status: WARN (1777587773.7174382)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### bridge_course_section_teachers

- Test severity: error
- Dagster current status: PASSED (1776891442.1797686)
- BQ probe: over-spec
- Grain status: suspect
- Findings:
  - **suspect**: declared ('course_section_key', 'staff_key', 'role',
    'effective_start_date') unique, but ('course_section_key', 'staff_key',
    'effective_start_date') is also unique → test over-specified
- Difficulty: TBD
- Disposition: TBD

### bridge_course_section_terms

- Test severity: error
- Dagster current status: PASSED (1776891735.8062124)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### bridge_student_contacts

- Test severity: error
- Dagster current status: WARN (1777488389.3015149)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### bridge_survey_expectations

- Test severity: error
- Dagster current status: PASSED (1777324708.9928725)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### bridge_survey_questions

- Test severity: error
- Dagster current status: PASSED (1777585227.3886392)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_assessment_administrations

- Test severity: error
- Dagster current status: PASSED (1777587703.6586652)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_assessment_comparisons

- Test severity: error
- Dagster current status: PASSED (1777415387.128835)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_assessment_goals

- Test severity: error
- Dagster current status: PASSED (1777415286.5392642)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_assessments

- Test severity: error
- Dagster current status: PASSED (1777585600.5180109)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_college_enrollments

- Test severity: error
- Dagster current status: PASSED (1776891754.6217651)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_colleges

- Test severity: error
- Dagster current status: PASSED (1776891747.8435695)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_course_sections

- Test severity: error
- Dagster current status: WARN (1777415288.7871072)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_courses

- Test severity: error
- Dagster current status: PASSED (1776891712.7175977)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_dates

- Test severity: error
- Dagster current status: PASSED (1776891763.3409421)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_job_candidates

- Test severity: error
- Dagster current status: PASSED (1776891727.6414225)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_job_postings

- Test severity: error
- Dagster current status: PASSED (1776891702.5147908)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_locations

- Test severity: error
- Dagster current status: PASSED (1777415387.3786857)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_regions

- Test severity: error
- Dagster current status: PASSED (1777414775.6625583)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_school_calendars

- Test severity: error
- Dagster current status: WARN (1777415287.039629)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_staff

- Test severity: error
- Dagster current status: PASSED (1776891443.9778259)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_staff_observation_expectations

- Test severity: error
- Dagster current status: PASSED (1777440445.7375019)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_staff_observation_goal_types

- Test severity: error
- Dagster current status: PASSED (1776891704.5221188)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_staff_observation_rubric_measurements

- Test severity: error
- Dagster current status: PASSED (1777440719.1336985)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_staff_observation_rubrics

- Test severity: error
- Dagster current status: PASSED (1776891718.0045002)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_staff_observation_types

- Test severity: error
- Dagster current status: PASSED (1777440440.1742857)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_staff_status

- Test severity: error
- Dagster current status: PASSED (1777324694.082113)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_staff_work_assignments

- Test severity: error
- Dagster current status: PASSED (1777324693.7319114)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_staffing_positions

- Test severity: error
- Dagster current status: PASSED (1777415286.7880406)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_student_attendance_intervention_types

- Test severity: error
- Dagster current status: PASSED (1777415386.8722026)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_student_contact_persons

- Test severity: error
- Dagster current status: PASSED (1777488141.5413485)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_student_enrollments

- Test severity: error
- Dagster current status: PASSED (1777415309.354219)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_student_section_enrollments

- Test severity: error
- Dagster current status: WARN (1777043375.6260455)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_students

- Test severity: error
- Dagster current status: PASSED (1776891705.0048437)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_survey_administrations

- Test severity: error
- Dagster current status: PASSED (1776891748.0129619)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_survey_questions

- Test severity: error
- Dagster current status: PASSED (1777585166.76543)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_surveys

- Test severity: error
- Dagster current status: PASSED (1777585159.6233733)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_terms

- Test severity: error
- Dagster current status: PASSED (1777415284.3611522)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_work_assignment_jobs

- Test severity: error
- Dagster current status: PASSED (1776891727.0040882)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_work_assignment_locations

- Test severity: error
- Dagster current status: WARN (1777415396.8623352)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_work_assignment_organizational_units

- Test severity: error
- Dagster current status: PASSED (1776891737.1321013)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_work_assignment_primary

- Test severity: error
- Dagster current status: PASSED (1777324698.9604256)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_work_assignment_reporting_relationships

- Test severity: error
- Dagster current status: PASSED (1777324890.7694252)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_work_assignment_status

- Test severity: error
- Dagster current status: PASSED (1776891745.554972)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### dim_work_assignment_types

- Test severity: error
- Dagster current status: PASSED (1776891726.1022213)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_assessment_scores_enrollment_scoped

- Test severity: error
- Dagster current status: WARN (1777588007.428239)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_assessment_scores_student_scoped

- Test severity: error
- Dagster current status: WARN (1777587993.2526362)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_behavioral_consequences

- Test severity: error
- Dagster current status: PASSED (1776891755.6137688)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_behavioral_incidents

- Test severity: error
- Dagster current status: WARN (1777415639.5386107)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_family_communications

- Test severity: error
- Dagster current status: PASSED (1776891449.4795532)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_grades_assignments

- Test severity: error
- Dagster current status: PASSED (1777043605.7868702)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_grades_category

- Test severity: error
- Dagster current status: PASSED (1777043582.4439588)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_grades_gpa

- Test severity: error
- Dagster current status: PASSED (1776891448.2503579)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_grades_term

- Test severity: error
- Dagster current status: WARN (1777043580.7230778)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_job_candidate_applications

- Test severity: error
- Dagster current status: PASSED (1777415286.296669)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_staff_attrition

- Test severity: error
- Dagster current status: PASSED (1777324902.2490525)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_staff_benefits_enrollments

- Test severity: error
- Dagster current status: PASSED (1776891712.9274178)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_staff_membership_enrollments

- Test severity: error
- Dagster current status: PASSED (1776891709.0663364)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_staff_observation_goals

- Test severity: error
- Dagster current status: PASSED (1777324891.1306014)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_staff_observation_scores

- Test severity: error
- Dagster current status: PASSED (1776891436.8779833)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_staff_observations

- Test severity: error
- Dagster current status: PASSED (1777440994.0969236)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_student_attendance_daily

- Test severity: error
- Dagster current status: WARN (1777415640.7186666)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_student_attendance_interventions

- Test severity: error
- Dagster current status: WARN (1777415644.9566367)
- BQ probe: dupes
- Grain status: broken
- Findings:
  - **broken**: BQ probe found 1632 dup rows on
    ('student_attendance_intervention_key',)
  - **status_mismatch**: probe found dupes, Dagster PASSED
- Difficulty: TBD
- Disposition: TBD

### fct_student_attendance_streaks

- Test severity: error
- Dagster current status: PASSED (1776891732.3214266)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_support_tickets

- Test severity: error
- Dagster current status: PASSED (1777415293.3660598)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_survey_responses

- Test severity: error
- Dagster current status: WARN (1777585232.0860147)
- BQ probe: dupes
- Grain status: broken
- Findings:
  - **broken**: BQ probe found 2458 dup rows on ('survey_response_key',)
  - **status_mismatch**: probe found dupes, Dagster PASSED
- Difficulty: TBD
- Disposition: TBD

### fct_survey_submissions

- Test severity: error
- Dagster current status: PASSED (1776891761.877206)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_work_assignment_additional_earnings

- Test severity: error
- Dagster current status: PASSED (1776891763.5232189)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD

### fct_work_assignment_compensation

- Test severity: error
- Dagster current status: PASSED (1776891763.6694102)
- BQ probe: unique
- Grain status: pass
- Difficulty: TBD
- Disposition: TBD
