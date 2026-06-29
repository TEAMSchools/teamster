# Focus School Software REST API — extracted reference

> Source: `https://kippfl.focusschoolsoftware.com/focus/api/docs/` — the page
> embeds the full spec as a `window.App` JS object (rendered client-side).
> Parsed here from that object; raw JSON in `focus-api-spec.json`. Field objects
> carry only `title`/`type`/`ref` — the source has **no per-field descriptions
> or required flags** on write bodies.

## Auth

OAuth2 `client_credentials`: `POST /token` with `client_id` + `client_secret` +
`scope`, returns a Bearer token. Provisioned via Focus _Third Party Systems_
setup (select the "Focus" API dialect, grant read/write scope, scope to
schools); Focus issues a Client ID/Secret per integration.

## Route inventory (314 routes, 74 groups)

| Group                                         | GET | POST | PUT | DELETE |
| --------------------------------------------- | --: | ---: | --: | -----: |
| addresses                                     |   4 |    0 |   0 |      0 |
| admins                                        |   3 |    0 |   0 |      0 |
| assignment_categories                         |   4 |    0 |   2 |      1 |
| assignments                                   |   3 |    2 |   2 |      1 |
| attendance                                    |   2 |    0 |   0 |      0 |
| attendance_codes                              |   2 |    0 |   2 |      0 |
| attendance_school                             |   2 |    0 |   0 |      0 |
| calendar_dates                                |   2 |    0 |   2 |      0 |
| calendar_dates_events                         |   2 |    0 |   0 |      0 |
| calendars                                     |   3 |    0 |   2 |      0 |
| contact_details                               |   2 |    0 |   0 |      0 |
| contacts                                      |   4 |    0 |   0 |      0 |
| course_periods                                |   4 |    0 |   0 |      0 |
| courses                                       |   4 |    0 |   0 |      0 |
| demographics                                  |   2 |    0 |   0 |      0 |
| discipline_actions                            |   2 |    0 |   0 |      0 |
| discipline_incidents                          |   3 |    0 |   0 |      0 |
| discipline_incidents_students                 |   2 |    0 |   0 |      0 |
| enrollment_codes                              |   2 |    0 |   2 |      0 |
| enrollments                                   |   6 |    0 |   0 |      0 |
| erp_facilities                                |   2 |    0 |   0 |      0 |
| erp_purchase_orders                           |   2 |    0 |   0 |      0 |
| erp_vendors                                   |   2 |    0 |   0 |      0 |
| final_grades                                  |   2 |    0 |   0 |      0 |
| grade_levels                                  |   2 |    0 |   2 |      0 |
| grade_posting_schemes                         |   2 |    0 |   2 |      0 |
| grade_posting_weights                         |   2 |    0 |   2 |      0 |
| grades                                        |   2 |    0 |   2 |      1 |
| gradingPeriods_ed_fi                          |   2 |    0 |   0 |      0 |
| grading_scales                                |   2 |    0 |   2 |      0 |
| graduation_subject_programs                   |   2 |    0 |   0 |      0 |
| locations                                     |   2 |    0 |   0 |      0 |
| log_entries                                   |   1 |    0 |   0 |      0 |
| logs                                          |   4 |    0 |   2 |      0 |
| marking_period_courses                        |   2 |    0 |   0 |      0 |
| marking_periods                               |   3 |    0 |   2 |      0 |
| marking_periods_oneroster                     |   2 |    0 |   0 |      0 |
| master_courses                                |   2 |    0 |   0 |      0 |
| multi                                         |   0 |    1 |   0 |      0 |
| parents                                       |   3 |    0 |   0 |      0 |
| period_schedules                              |   2 |    0 |   2 |      0 |
| periods                                       |   2 |    0 |   2 |      0 |
| profiles                                      |   2 |    0 |   2 |      0 |
| progression_plans                             |   2 |    0 |   0 |      0 |
| ps_fees                                       |   2 |    0 |   2 |      0 |
| quarters                                      |   2 |    0 |   0 |      0 |
| report_card_grades                            |   2 |    0 |   2 |      0 |
| school_enrollments                            |   6 |    0 |   0 |      0 |
| schools                                       |  31 |    0 |   2 |      0 |
| sections                                      |  17 |    2 |   4 |      1 |
| semesters                                     |   3 |    0 |   0 |      0 |
| sessions_ed_fi                                |   2 |    0 |   0 |      0 |
| staff                                         |   2 |    0 |   0 |      0 |
| staff_organization_association                |   2 |    0 |   0 |      0 |
| student                                       |   2 |    2 |   2 |      0 |
| student_academic_record                       |   2 |    0 |   0 |      0 |
| student_grades                                |   2 |    0 |   0 |      0 |
| student_groups                                |   6 |    0 |   0 |      0 |
| student_organization_association              |   2 |    0 |   0 |      0 |
| student_program_associations                  |   2 |    0 |   0 |      0 |
| student_report_card_grades                    |   2 |    0 |   2 |      0 |
| student_schedule                              |   2 |    0 |   2 |      0 |
| student_special_eduation_program_associations |   2 |    0 |   0 |      0 |
| student_title_i_program_associations          |   2 |    0 |   0 |      0 |
| students                                      |   9 |    0 |   0 |      0 |
| teachers                                      |   6 |    0 |   0 |      0 |
| token                                         |   0 |    1 |   0 |      1 |
| userProfiles                                  |   4 |    0 |   0 |      0 |
| user_addresses                                |   2 |    0 |   0 |      0 |
| user_contacts                                 |   2 |    0 |   0 |      0 |
| user_profiles                                 |   2 |    0 |   2 |      1 |
| user_users                                    |   2 |    0 |   0 |      0 |
| users                                         |  15 |    1 |   3 |      1 |
| years                                         |   3 |    0 |   0 |      0 |

## Write endpoints relevant to enrollment intake

### Create student — `POST /student`

Body fields: `uuid`, `student`, `focus_id`, `school_mint_id`, `first_name`,
`middle_name`, `last_name`, `birthdate`, `gender`, `email`, `ethnicity`,
`white`, `black`, `asian`, `island_pacific`, `american_indian`, `ese_status`,
`current_grade`, `accepting_grade`, `accepting_program`, `preferred_language`,
`current_school`, `accepting_school`, `school_year`, `guardian_1_first_name`,
`guardian_1_last_name`, `guardian_1_relationship`, `guardian_1_home_phone`,
`guardian_1_mobile_phone`, `guardian_1_work_phone`, `guardian_1_email`,
`guardian_1_sso_parent_id`, `guardian_2_first_name`, `guardian_2_last_name`,
`guardian_2_relationship`, `guardian_2_home_phone`, `guardian_2_mobile_phone`,
`guardian_2_work_phone`, `guardian_2_email`, `address`, `address2`, `city`,
`state`, `zipcode`, `home_address`, `guardian_1`, `guardian_2`

### Update student — `PUT /student/:uuid`

Body fields: `uuid`, `student`, `focus_id`, `school_mint_id`, `first_name`,
`middle_name`, `last_name`, `birthdate`, `gender`, `email`, `ethnicity`,
`white`, `black`, `asian`, `island_pacific`, `american_indian`, `ese_status`,
`current_grade`, `accepting_grade`, `accepting_program`, `preferred_language`,
`current_school`, `accepting_school`, `school_year`, `guardian_1_first_name`,
`guardian_1_last_name`, `guardian_1_relationship`, `guardian_1_home_phone`,
`guardian_1_mobile_phone`, `guardian_1_work_phone`, `guardian_1_email`,
`guardian_1_sso_parent_id`, `guardian_2_first_name`, `guardian_2_last_name`,
`guardian_2_relationship`, `guardian_2_home_phone`, `guardian_2_mobile_phone`,
`guardian_2_work_phone`, `guardian_2_email`, `address`, `address2`, `city`,
`state`, `zipcode`, `home_address`, `guardian_1`, `guardian_2`

### Upsert user (guardian/contact) — `PUT /users`

Body fields: `uuid`, `local_id`, `district_id`, `state_id`, `role`, `username`,
`title`, `first_name`, `middle_name`, `last_name`, `suffix`, `birthdate`,
`gender`, `email`, `school_uuids`, `gradelevels`, `linked_user_uuids`,
`address_uuids`, `updated_at`, `active`, `image`, `image_date`

### Batch — `POST /multi`

Body fields: `calls`

> Note: `enrollments` / `school_enrollments` are **GET-only** — creating the
> enrollment record itself may require the SFTP `STUDENT_ENROLLMENT` template
> even when using the API for the student record (`POST /student` carries
> `accepting_grade/school/program` + `school_year`; whether that creates the
> enrollment is a vendor-confirm item).
