# Column Naming Audit — Star Schema Mart Models

90 columns across 40+ models use source-system or KIPP-specific names. Grouped
by category with proposed renames. Mark each: ✅ accept, ❌ reject, or ✏️ alt.

## 1. Student identifier (15 models)

Spec says: `student_number` → `local_student_identifier`

Note: `dim_students` already uses `local_student_identifier`. All other models
use `student_number`. This is a degenerate dimension for filtering — renaming
changes surrogate key inputs in some models.

| Current          | Proposed                   | Models                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ---------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `student_number` | `local_student_identifier` | dim_college_enrollments, dim_student_assessment_expectations, dim_student_section_enrollments, bridge_student_contacts, fct_assessment_scores_enrollment_scoped, fct_assessment_scores_student_scoped, fct_behavioral_incidents, fct_family_communications, fct_grades_assignments, fct_grades_category, fct_grades_gpa, fct_grades_term, fct_student_attendance_daily, fct_student_attendance_interventions, fct_student_attendance_streaks |

## 2. Staff identifier (9 models)

`employee_number` is KIPP-generated, not a standard term.

| Current                     | Proposed                     | Models                                                                                                                                                                      |
| --------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `employee_number`           | `local_staff_identifier`     | dim_staff, dim_staff_observation_expectations, dim_staff_work_assignments, bridge_course_section_teachers, fct_staff_benefits_enrollments, fct_staff_membership_enrollments |
| `teacher_employee_number`   | `teacher_staff_identifier`   | fct_staff_observations, fct_staff_observation_microgoals                                                                                                                    |
| `observer_employee_number`  | `observer_staff_identifier`  | fct_staff_observations                                                                                                                                                      |
| `teammate_employee_number`  | `teammate_staff_identifier`  | dim_staffing_positions                                                                                                                                                      |
| `recruiter_employee_number` | `recruiter_staff_identifier` | dim_staffing_positions                                                                                                                                                      |

## 3. Person name fields (dim_staff, dim_work_assignment_reporting_relationships)

ADP-specific naming (`family_name_1`, `formatted_name`).

| Current                  | Proposed             | Models                                      |
| ------------------------ | -------------------- | ------------------------------------------- |
| `formatted_name`         | `full_name`          | dim_staff                                   |
| `family_name_1`          | `last_name`          | dim_staff                                   |
| `given_name`             | `first_name`         | dim_staff                                   |
| `manager_formatted_name` | `manager_full_name`  | dim_work_assignment_reporting_relationships |
| `manager_family_name_1`  | `manager_last_name`  | dim_work_assignment_reporting_relationships |
| `manager_given_name`     | `manager_first_name` | dim_work_assignment_reporting_relationships |

## 4. System account fields (dim_staff)

| Current            | Proposed             | Models    |
| ------------------ | -------------------- | --------- |
| `sam_account_name` | `ad_username`        | dim_staff |
| `google_email`     | `organization_email` | dim_staff |

## 5. ADP work assignment nested structs (dim_staff_work_assignments)

These are ADP API paths flattened into column names.

| Current                                                             | Proposed                      |
| ------------------------------------------------------------------- | ----------------------------- |
| `item_id`                                                           | `assignment_id`               |
| `pay_cycle_code__code_value`                                        | `pay_cycle_code`              |
| `payroll_file_number`                                               | `payroll_number`              |
| `payroll_group_code`                                                | `payroll_group`               |
| `payroll_schedule_group_id`                                         | `payroll_schedule_group`      |
| `standard_hours__hours_quantity`                                    | `standard_hours`              |
| `standard_hours__unit_code__code_value`                             | `standard_hours_unit`         |
| `standard_pay_period_hours__hours_quantity`                         | `standard_pay_period_hours`   |
| `wage_law_coverage__coverage_code__code_value`                      | `wage_law_coverage_code`      |
| `wage_law_coverage__coverage_code__name`                            | `wage_law_coverage_name`      |
| `wage_law_coverage__wage_law_name_code__code_value`                 | `wage_law_code`               |
| `wage_law_coverage__wage_law_name_code__name`                       | `wage_law_name`               |
| `worker_time_profile__badge_id`                                     | `time_badge_id`               |
| `worker_time_profile__time_and_attendance_indicator`                | `is_time_tracked`             |
| `worker_time_profile__time_zone_code`                               | `time_zone`                   |
| `worker_time_profile__time_service_supervisor__associate_oid`       | `time_supervisor_id`          |
| `worker_time_profile__time_service_supervisor__position_id`         | `time_supervisor_position_id` |
| `worker_time_profile__time_service_supervisor__worker_id__id_value` | `time_supervisor_worker_id`   |

## 6. ADP reporting relationship IDs (dim_work_assignment_reporting_relationships)

| Current                 | Proposed                               |
| ----------------------- | -------------------------------------- |
| `manager_associate_oid` | `manager_id`                           |
| `manager_worker_id`     | `manager_worker_identifier`            |
| `manager_position_id`   | `manager_position_id` (keep — generic) |

## 7. ADP worker type (dim_work_assignment_types)

| Current            | Proposed               |
| ------------------ | ---------------------- |
| `worker_type_code` | `assignment_type_code` |
| `worker_type_name` | `assignment_type_name` |

## 8. PowerSchool identifiers

| Current                 | Proposed                    | Models                                                      |
| ----------------------- | --------------------------- | ----------------------------------------------------------- |
| `powerschool_school_id` | `sis_school_id`             | dim_locations, dim_student_assessment_expectations          |
| `deanslist_school_id`   | `behavior_system_school_id` | dim_locations                                               |
| `powerschool_term_id`   | `sis_term_id`               | dim_terms                                                   |
| `powerschool_year_id`   | `sis_year_id`               | dim_terms                                                   |
| `powerschool_person_id` | `contact_person_id`         | dim_student_contact_persons                                 |
| `sections_dcid`         | `section_id`                | bridge_course_section_teachers, bridge_course_section_terms |
| `teachernumber`         | `teacher_number`            | bridge_course_section_teachers                              |
| `school_id`             | `sis_school_id`             | dim_assessment_targets, dim_terms                           |

## 9. dbt internal (dim_student_contact_persons)

| Current                | Proposed                    |
| ---------------------- | --------------------------- |
| `_dbt_source_relation` | remove (or derive `region`) |

## 10. Source-system record IDs (degenerate dimensions)

These are IDs consumers use for cross-referencing with source systems. Renaming
these has lower value — they're intentionally source-specific for traceability.

| Current                | Proposed            | Recommendation                         |
| ---------------------- | ------------------- | -------------------------------------- |
| `survey_id`            | keep                | 5 models — generic enough              |
| `survey_response_id`   | keep                | 2 models — generic enough              |
| `incident_id`          | keep                | 2 models — generic enough              |
| `incident_penalty_id`  | `consequence_id`    | fct_behavioral_consequences            |
| `candidate_id`         | keep                | 2 models — generic enough              |
| `assessment_id`        | keep                | 1 model — generic enough               |
| `rubric_id`            | keep                | 2 models — domain-specific but generic |
| `measurement_id`       | keep                | 2 models — generic                     |
| `measurement_group_id` | keep                | 2 models — generic                     |
| `goal_tag_id`          | `microgoal_type_id` | dim_staff_observation_microgoal_types  |
| `staffing_model_id`    | `position_id`       | dim_staffing_positions                 |
| `college_code_branch`  | `institution_code`  | dim_colleges, dim_college_enrollments  |

## Summary

| Category           | Column count     | Rename scope             |
| ------------------ | ---------------- | ------------------------ |
| Student identifier | 15               | Single rename, 15 models |
| Staff identifier   | 9                | Single rename, 9 models  |
| Person names       | 6                | 2 models                 |
| System accounts    | 2                | 1 model                  |
| ADP nested structs | 18               | 1 model                  |
| ADP reporting      | 3                | 1 model                  |
| ADP worker type    | 2                | 1 model                  |
| PowerSchool IDs    | 8                | 5 models                 |
| dbt internal       | 1                | 1 model                  |
| Source record IDs  | 3 renames of ~12 | 3 models                 |
| **Total**          | **67 renames**   | **~25 models**           |
