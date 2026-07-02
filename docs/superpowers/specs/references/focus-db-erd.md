# Focus SIS database (Postgres) — ERD reference

> Source: "Focus DB Diagram.pdf" (2024 User Conference FOCUS Database, ERD
> Diagram; Focus School Software). A partial ERD in Crow's Foot notation
> covering the most-queried tables. Errors/omissions →
> `smooth@focusschoolsoftware.com`.
>
> This is the **database** schema (what the `dlt/focus` pull loads from the
> Focus Postgres `public` schema into `dagster_kippmiami_dlt_focus`). For the
> REST API surface, see `focus-api-spec.md`. For warehouse-query gotchas
> (soft-delete sentinel, `custom_NNN` decode, join pitfalls), see
> `src/dbt/focus/CLAUDE.md`.

## Conventions

- **PK / FK** — Crow's Foot notation; a PK holds one distinct value, an FK may
  repeat (many-to-one).
- **`syear`** — school-year start year (e.g. `2026` = SY2026-27), matching
  Finalsite `school_year_start` and the `focus_enrollment_start_date_floor` var
  convention.
- **`school_id`** joins to `schools.id`; the district-facing school number is
  `schools.custom_327`. **`district_id`** joins to `districts.id`.
- **Soft delete** — `deleted` is `NULL` for live rows and `1` for deleted, never
  `0` (see `src/dbt/focus/CLAUDE.md`).

## Attendance calendar — singular vs plural (the trap)

Two distinct tables, easy to confuse:

| Table                  | Grain                         | Key columns                                                            |
| ---------------------- | ----------------------------- | ---------------------------------------------------------------------- |
| `attendance_calendars` | one row per calendar (header) | PK `calendar_id`, FK `school_id`, `syear`, `title`, `default_calendar` |
| `attendance_calendar`  | **one row per calendar day**  | PK `id`, FK `calendar_id`, FK `school_id`, `syear`, **`school_date`**  |

`student_enrollment.calendar_id` → `attendance_calendars.calendar_id` (the
header). The **actual in-session dates** live in the singular
`attendance_calendar`, keyed back to the header by `calendar_id`.

**First day of school** for a school year = `min(school_date)` in
`attendance_calendar` for that `syear` (scope to the school's default calendar
via `attendance_calendars.default_calendar`). This is the authoritative,
registrar-maintained source for the enrollment start-date floor — independent of
the Finalsite feed.

Ingestion note: the `dlt/focus` pull historically loaded only
`attendance_calendars` (header); `attendance_calendar` (dates) was added to
`src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml` so the dates
land in the warehouse.

## Students, people, contacts

| Table                    | PK           | Key FKs / columns                                                                                           |
| ------------------------ | ------------ | ----------------------------------------------------------------------------------------------------------- |
| `students`               | `student_id` | `first_name`, `middle_name`, `last_name`, `custom_fields` (jsonb), `custom_*`                               |
| `students_join_users`    | `id`         | FK `student_id`, `person_id`, `staff_id`                                                                    |
| `students_join_people`   | `id`         | FK `student_id`, `person_id`; `student_relation`, `sort_order`, `pickup`, `custody`, `emergency`, `deleted` |
| `students_join_students` | `id`         | FK `primary_student_id`, `secondary_student_id`                                                             |
| `students_join_groups`   | `id`         | FK `group_id`, `student_id` (→ `student_groups.id`)                                                         |
| `students_join_address`  | `id`         | FK `student_id`, `address_id`                                                                               |
| `address`                | `address_id` | `address`, `address2`, `city`, `state`, `zipcode`                                                           |
| `people`                 | `person_id`  | `first_name`, `middle_name`, `last_name`, `title`, `deleted`                                                |
| `people_join_contacts`   | `id`         | FK `person_id`; `title`, `value`, `callout`, `sms`                                                          |

`students` is the hub: `student_id` fans out to enrollment, attendance,
schedule, grades, discipline, SSS. Guardian/contact chain: `students` →
`students_join_people` → `people` → `people_join_contacts`.

## Student enrollment

`student_enrollment` (PK `id`) is the enrollment stint. Key FKs:

- `student_id` → `students.student_id`
- `school_id` → `schools.id`; `district_id` → `districts.id`
- `grade_id` → `school_gradelevels.id`
- `enrollment_code` → `student_enrollment_codes.id` (rows of `type` = Add)
- `drop_code` → `student_enrollment_codes.id` (rows of `type` = Drop)
- `calendar_id` → `attendance_calendars.calendar_id`
- `team_id` → `scheduling_teams.id`
- `graduation_requirement_program` → `grad_subject_programs.id`
- plus `start_date`, `end_date`, `syear`

Supporting: `student_enrollment_codes` (PK `id`, `short_name`, `title`, `type`),
`school_gradelevels` (PK `id`, FK `school_id`, `short_name`, `title`),
`scheduling_teams`, `grad_subject_programs`.

## Attendance (day and period)

| Table                  | PK                  | Key FKs / columns                                                                                                                  |
| ---------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `attendance_day`       | `id`                | FK `student_id`, `marking_period_id`; `syear`, `school_date`, `daily_code`, `state_value`                                          |
| `attendance_notes`     | `id`                | FK `attendance_day_id`, `student_id`                                                                                               |
| `attendance_period`    | `id`                | FK `period_id`, `course_period_id`, `student_id`, `attendance_code`, `attendance_teacher_code`, `marking_period_id`; `school_date` |
| `attendance_completed` | `id`                | FK `staff_id`, `school_id`, `period_id`, `course_period_id`; `school_date`, `syear`                                                |
| `attendance_codes`     | `id`                | FK `school_id`; `syear`, `short_name`, `title`                                                                                     |
| `marking_periods`      | `marking_period_id` | FK `school_id`; `syear`, `short_name`, `title`, `start_date`, `end_date`                                                           |

`attendance_day` = daily attendance per student; `attendance_period` = per
class-period attendance. `attendance_code` / `attendance_teacher_code` →
`attendance_codes.id`.

## Courses, course periods, schedule

| Table             | PK                 | Key FKs / columns                                                                                                                                                                                                                                           |
| ----------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `master_courses`  | `course_id`        | FK `district_id`; `syear`, `short_name`                                                                                                                                                                                                                     |
| `courses`         | `course_id`        | FK `school_id`, `grad_subject_id`(`_2`,`_3`), `subject_id`, `store_category_id`; `syear`, `short_name`, `title`                                                                                                                                             |
| `course_subjects` | `subject_id`       | FK `school_id`; `short_name`, `title`                                                                                                                                                                                                                       |
| `course_periods`  | `course_period_id` | FK `school_id`, `course_id`, `teacher_id`, `co_teacher_id1`–`10`, `marking_period_id`, `period_id`, `end_period_id`, `room`, `calendar_id`, `team_id`, `bell_schedule_id`, `grade_posting_scheme_id`, `grade_scale_id`, `standards_grade_scale_id`; `syear` |
| `schedule`        | `id`               | FK `school_id`, `student_id`, `course_id`, `course_period_id`, `marking_period_id`; `syear`, `start_date`, `end_date`                                                                                                                                       |
| `school_periods`  | `period_id`        | FK `school_id`                                                                                                                                                                                                                                              |
| `co_teachers`     | —                  | FK `staff_id`, `course_period_id`, `school_id`                                                                                                                                                                                                              |
| `co_teacher_days` | `id`               | FK `teacher_id`                                                                                                                                                                                                                                             |

`course_periods` is the section (a course taught in a period by a teacher);
`schedule` links a `student_id` to a `course_period_id`.

## Grades, standards, gradebook

- `student_report_card_grades` (PK `id`) — FK `school_id`, `student_id`,
  `report_card_comment_id`, `report_card_grade_id`, `grade_scale_id`,
  `marking_period_id`; `percent_grade`, `grade_title`, `credits`,
  `credits_earned`, `course_num`, `course_title`, `syear`, FK `course_id`,
  `grad_subject_id`.
- `report_card_grades` (PK `id`) — FK `scale_id`, `school_id`; `grade_title`.
- `report_card_grade_scales` (PK `id`) — `syear`, FK `school_id`,
  `default_scale`.
- `report_card_comments`, `student_report_card_grades_change_requests`,
  `grade_change_request_reasons`.
- `grad_subjects` / `grad_subject_credits` / `grad_subject_programs` /
  `grad_subject_credit_course` / `grad_subject_credit_assessment` — graduation
  requirement structure.
- Standards: `student_standard_grades` (PK `id`; FK `standard_id`, `course_id`,
  `course_period_id`, `student_id`, `marking_period_id`, `grade_scale_id`,
  `report_card_grade_id`), `standards` (FK `category_1_id`..`category_4_id`),
  `standard_categories_1`..`_4` (FK `rollover_id`), `standards_join_courses`.
- Gradebook: `gradebook_grades` (FK `student_id`, `assignment_id`,
  `standard_id`, `letter_grade`, `comment_codes`), `gradebook_assignments` (PK
  `assignment_id`; FK `template_id`, `rubric_id`, `assignment_type_id`),
  `gradebook_assignment_types`, `gradebook_templates` (FK `staff_id`, `schools`
  delimited), `gradebook_*_join_course_periods`, `gradebook_comment_codes`.

## Discipline

`discipline_incidents` (PK `id`, FK `school_id`, `syear`) and
`discipline_referrals` (PK `referral_id`; FK `attendance_code`,
`attendance_period_id`, `school_id`, `student_id`, `merged_referral_id`,
`tardy_threshold_id`; `referral_date`, `suspension_begin`, `suspension_end`)
link via `discipline_incidents_join_referrals`. Codes/actions: `referral_codes`,
`referral_code_offenses`, `referral_actions`, `referral_teacher_codes`,
`tardy_threshold` (+ `_attendance_code`, `_school_period`), `letters` /
`letter_queue` / `letter_triggers`.

Note: `discipline_referrals` and `discipline_incidents` are custom-field
`source_class` targets (see below).

## Test history

`test_history_administrations` (PK `id`; FK `test_id`, `student_id`,
`fas_assignment_id`; `administration_date`) → `test_history_scores` (FK
`administration_id`, `test_id`, `part_id`, `score_type_id`, `fas_section_id`,
`student_id`; `test_code`, `score`). Reference: `test_history_tests`,
`test_history_test_types`, `test_history_parts`, `test_history_score_types`,
`test_history_score_ranges` (+ `_sublevels`), `eoc_scale` / `eoc_scale_sets`.

## Users

`users` (PK `staff_id`; `username`, `last_name`, `first_name`, `middle_name`,
`ein`, FK `profiles`, `school_id`). Related: `user_enrollment` (FK `staff_id`,
`profiles`, `erp_profiles`, `schools`; `start_date`, `end_date`),
`user_profiles`, `permission` (FK `profile_id`, `key`), `user_permission`,
`user_join_groups`, `login_history`, `teacher_student_flags`, `saved_reports`,
`user_page_favorite`, `email_verification`, `email_notifications`.

## Custom fields (critical for querying)

The custom-field system spans several tables:

- `custom_fields` (PK `id`) — the field **definition** catalog: `source_id`,
  `source_class`, `type`, `code`, `column_name`, `alias`, `json`, `required`,
  `deleted`, `computed_query`, `default_value`, `fallback_value`, `system`.
- `custom_field_select_options` (PK `id`) — allowed values for `select` /
  `multiple` fields: `source_id`, `source_class`, `code`, `label`.
- `custom_field_log_columns` / `custom_field_log_entries` — `log`-type field
  values.
- `custom_fields_join_categories`, `custom_field_categories`,
  `custom_field_categories_join_schools`,
  `custom_field_categories_join_profiles`.

**`source_class` → entity table + key** (join `custom_fields.source_id` to):

| `source_class`          | Table                  | Key          |
| ----------------------- | ---------------------- | ------------ |
| `SISStudent`            | `students`             | `student_id` |
| `FocusUser`             | `users`                | `staff_id`   |
| `SISSchool`             | `schools`              | `id`         |
| `SISDistrict`           | `districts`            | `id`         |
| `SISDisciplineReferral` | `discipline_referrals` | `id`         |
| `SISDisciplineIncident` | `discipline_incidents` | `id`         |

**Value storage by field `type`:**

| Type                          | Stored as                                                                                      |
| ----------------------------- | ---------------------------------------------------------------------------------------------- |
| `checkbox`                    | char — `null`, `N`, or `Y`                                                                     |
| `date`                        | timestamp                                                                                      |
| `select`                      | `bigint` → `custom_field_select_options.id`                                                    |
| `multiple`                    | delimited list of `custom_field_select_options.id`                                             |
| `numeric`                     | numeric                                                                                        |
| `text` / `textarea`           | text                                                                                           |
| `signature` / `time`          | varchar                                                                                        |
| `json`                        | key/value pairs in `students.custom_fields` (jsonb); key = `column_name`                       |
| `computed` / `computed_table` | not materialized — query lives in `custom_fields.computed_query`, resolvable only inside Focus |
| `file`                        | pointer to `focus_files.source_id`                                                             |
| `holder`                      | UI layout placeholder (no data)                                                                |
| `log`                         | pointer to `custom_field_log_entries`                                                          |

Values live inline on the entity's wide `custom_NNN` columns (e.g.
`students.custom_327` = school number on `schools`). See
`src/dbt/focus/CLAUDE.md` for the decode mechanics (match stored value against
both `id` and `code`; `column_name` is uppercase in the catalog but lowercase on
the entity table; filter `custom_field_select_options.source_class`).

## Other domains (table inventories)

- **School choice** — `school_choice_applications`, `_application_status`,
  `_application_notes`, `_status`, `_programs`, `_program_categories`,
  `_program_continuities`, `_program_seats`, `_zones`, `_tours_auditions` (+
  `_types`).
- **SSS (student support services)** — events/forms (`sss_events`,
  `sss_event_instances`, `sss_forms`, `sss_form_instances`, `sss_event_steps` /
  `_step_instances`, `sss_accommodations` (+ options / categories),
  `sss_meeting_minutes`, `sss_tasks`, `sss_programs`, `sss_permissions`) and
  goals/caseload (`sss_goals`, `sss_pmp_goals`, `sss_pmp_setup` /
  `_data_points`, `sss_services`, `sss_service_code` (+ `_provider`),
  `sss_caseload` / `_group` / `_service` (+ `_icd10`), `sss_progress_codes` /
  `_updates`).
- **Communication** — `communication_messages`, `_announcements`,
  `_message_schools` / `_profiles` / `_recipients`, `_attendance_messages`,
  `_schedules`, `_templates`, `_text`, `_audio`, `_queue`, `languages`.
- **Formbuilder** — `formbuilder_forms`, `_components`, `_data`, `_instances`,
  `_drafts`, `_revisions`, `_translations`, `_headers` / `_header_instances`,
  `_collections`, `_objects`, `_actions`, `_tags` / `_join_tags`,
  `_join_profiles`, `_form_fees`, `form_requests`.
