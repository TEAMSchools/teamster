# Focus SIS Phase B — plan index

Tracking + decisions index for Phase B (#4213): `stg_focus__*` staging,
`int_focus__*` intermediate, custom-field unpivot, and kipptaf integration. Live
status checklist is in **#4213**; this doc is the durable decisions +
batch-contents reference (replaces the gitignored working scaffold).

Design spec:
[`2026-04-03-focus-sis-integration-design.md`](../specs/2026-04-03-focus-sis-integration-design.md).
Residual (empty-source) tables: **#4220**.

## Batches (one plan doc + one PR each)

| Batch                    | Tables                                                                                                                                                                                                                                                                   | Plan doc                                         |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------ |
| A — Students / people    | `address`, `people_join_contacts`, `students` (3)                                                                                                                                                                                                                        | _tbd_                                            |
| B — Enrollment & org     | `student_enrollment`, `student_enrollment_codes`, `school_gradelevels`, `schools`, `districts`, `attendance_calendars`, `grad_subject_programs` (7) + `int_focus__student_enrollment`                                                                                    | _tbd_                                            |
| C — Attendance lookups   | `attendance_codes`, `attendance_completed`, `marking_periods`, `school_periods` (4)                                                                                                                                                                                      | `2026-06-18-focus-staging-attendance-lookups.md` |
| D — Courses & scheduling | `courses`, `course_periods`, `course_subjects`, `course_weights`, `master_courses`, `course_code_directory`, `co_teacher_days`, `resources` (8)                                                                                                                          | _tbd_                                            |
| E — Grades & standards   | `report_card_grades`, `report_card_grade_scales`, `report_card_comments`, `grad_subjects`, `grad_subject_credits`, `standards`, `standard_categories_1`–`4`, `standards_join_courses`, `gradebook_assignments`, `gradebook_assignment_types`, `gradebook_templates` (14) | _tbd_                                            |
| F — Discipline lookups   | `referral_actions`, `referral_codes` (2)                                                                                                                                                                                                                                 | _tbd_                                            |
| G — Users & permissions  | `users`, `user_enrollment`, `user_profiles`, `permission`, `login_history` (5)                                                                                                                                                                                           | _tbd_                                            |
| H — Custom fields        | `custom_fields`, `custom_field_categories`, `custom_field_select_options`, `custom_field_log_columns`, `custom_field_log_entries`, `custom_fields_join_categories` (6) + custom-field unpivot model                                                                      | _tbd_                                            |
| I — Test history         | `test_history_tests`, `test_history_test_types`, `test_history_parts`, `test_history_score_types`, `test_history_score_ranges` (5)                                                                                                                                       | _tbd_                                            |
| kipptaf integration      | `models/focus/sources-kippmiami.yml` + `stg_kippmiami__focus__*` wrappers                                                                                                                                                                                                | _tbd_                                            |

54 populated tables total. The 22 empty tables (`attendance_day` /
`attendance_period`, `schedule`, `gradebook_grades`,
`student_report_card_grades`, the `discipline_*` domain, `students_join_*`,
`people`, etc.) are out of scope here — #4220.

## Resolved decisions

- **Wide / custom-heavy tables** (`students` 565 cols / 510 custom,
  `course_periods` 289, `users` 235, `master_courses` 109, `schools` 85,
  `student_enrollment` 62): contract-enforced staging carries **curated core
  columns**; the `custom_*` long-tail unpivots to a long key/value model joined
  to the `custom_fields` / `custom_field_select_options` metadata crosswalk.
- **Curation anchor:** the Focus "Florida K-12 Import Layouts" mapping (Google
  Drive `1td8N9GkYuhvpa6rLPndoF1dxIN2sSICk`) — maps each import field to a Focus
  `table.column` with description/format/valid-codes. The mapped columns per
  table are the curated core set; the doc's DESCRIPTION/FORMAT supply staging
  `description:` text. Some meaningful fields map to specific `custom_NNN`
  columns (e.g. `schools.custom_327` = school number) — include those by name.
- **ERD** (Google Drive `1aoSOdVrlmcMmUlYQ7d0JiFJYLWxTJEY7`) — for
  `int_focus__student_enrollment` join keys and any `*_join_*` composite grains.
- **PK:** 42 tables have a literal `id`; 12 use entity-specific keys
  (`address_id`, `course_id`, `course_period_id`, `marking_period_id`,
  `period_id`, `student_id`/`profile_id`, etc.). Uniqueness test targets that
  key.
- **Soft-delete:** `deleted INT64` where `0` = live → `where deleted = 0` (NOT
  `is null`) on `address`, `schools`, `students`, `users`,
  `student_enrollment_codes`, and the `custom_*` tables. Variants `inactive` /
  `active` / `archived` on a few — confirm semantics per table.
- **Build context:** `stg_focus__*` build inside the **kippmiami** project
  (`focus_schema: dagster_kippmiami_dlt_focus` set there; `focus` package
  wired). Command:
  `uv run dbt build --select <model> --project-dir src/dbt/kippmiami`.
- **Conventions:** per `src/dbt/CLAUDE.md` — directory-level
  `contract: enforced`, uniqueness + `not_null` at `severity: error`,
  soft-delete filter in staging, exclude dlt bookkeeping (`_dlt_*`) and the
  audit-quad (`created_by_class`/`_id`, `updated_by_class`/`_id`),
  `description:` on model + every contracted column.

## Sequencing notes

- kipptaf integration ships last and in its own PR — the kipptaf source resolves
  to prod for `target=staging` CI, so district staging must land in prod first
  (see `src/dbt/CLAUDE.md` → "kipptaf source consumers of district columns").
- Batch C is the pattern-proving batch (narrow, no soft-delete/booleans/custom).
  Validate it before the wide batches (A, B, D, E, G, H).
