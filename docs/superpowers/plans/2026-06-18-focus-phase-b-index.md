# Focus SIS Phase B — plan index

Tracking + decisions index for Phase B (#4213): `stg_focus__*` staging,
`int_focus__*` intermediate, custom-field unpivot, and kipptaf integration. Live
status checklist is in **#4213**; this doc is the durable decisions +
batch-contents reference (replaces the gitignored working scaffold).

Design spec:
[`2026-04-03-focus-sis-integration-design.md`](../specs/2026-04-03-focus-sis-integration-design.md).
Residual (empty-source) tables: **#4220**.

## Batches (one plan doc + one PR each)

| Batch                     | Tables                                                                                                                                                                                                                                                                                             | Plan doc                                           |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| A — Students / people     | `address`, `people_join_contacts`, `students` (3)                                                                                                                                                                                                                                                  | `2026-06-18-focus-staging-a-students-people.md`    |
| B — Enrollment & org      | `student_enrollment`, `student_enrollment_codes`, `school_gradelevels`, `schools`, `districts`, `attendance_calendars`, `grad_subject_programs` (7) + `int_focus__student_enrollment`                                                                                                              | `2026-06-18-focus-staging-b-enrollment.md`         |
| C — Attendance lookups    | `attendance_codes`, `attendance_completed`, `marking_periods`, `school_periods` (4)                                                                                                                                                                                                                | `2026-06-18-focus-staging-attendance-lookups.md`   |
| D — Courses & scheduling  | `courses`, `course_periods`, `course_subjects`, `course_weights`, `master_courses`, `course_code_directory`, `co_teacher_days`, `resources` (8)                                                                                                                                                    | `2026-06-18-focus-staging-d-courses.md`            |
| E — Grades & standards    | `report_card_grades`, `report_card_grade_scales`, `report_card_comments`, `grad_subjects`, `grad_subject_credits`, `standards`, `standard_categories_1`–`4`, `standards_join_courses`, `gradebook_assignments`, `gradebook_assignment_types`, `gradebook_templates` (14)                           | `2026-06-18-focus-staging-e-grades-standards.md`   |
| F — Discipline lookups    | `referral_actions`, `referral_codes` (2)                                                                                                                                                                                                                                                           | `2026-06-18-focus-staging-f-discipline-lookups.md` |
| G — Users & permissions   | `users`, `user_enrollment`, `user_profiles`, `permission`, `login_history` (5)                                                                                                                                                                                                                     | `2026-06-18-focus-staging-g-users.md`              |
| H — Custom field metadata | `custom_fields`, `custom_field_categories`, `custom_field_select_options`, `custom_field_log_columns`, `custom_field_log_entries`, `custom_fields_join_categories` (6) — staging only; NO unpivot (custom values are inline-aliased in their entity models). Powers the deferred decode follow-up. | _tbd_                                              |
| I — Test history          | `test_history_tests`, `test_history_test_types`, `test_history_parts`, `test_history_score_types`, `test_history_score_ranges` (5)                                                                                                                                                                 | `2026-06-18-focus-staging-i-test-history.md`       |
| kipptaf integration       | `models/focus/sources-kippmiami.yml` + `stg_kippmiami__focus__*` wrappers                                                                                                                                                                                                                          | _tbd_                                              |

54 populated tables total. The 22 empty tables (`attendance_day` /
`attendance_period`, `schedule`, `gradebook_grades`,
`student_report_card_grades`, the `discipline_*` domain, `students_join_*`,
`people`, etc.) are out of scope here — #4220.

## Resolved decisions

- **Wide / custom-heavy tables** (`students` 565 cols / 510 custom,
  `course_periods` 289, `users` 235, `master_courses` 109, `schools` 85,
  `student_enrollment` 62): contract-enforced staging carries the curated core
  columns **plus all currently-populated `custom_*` columns, each directly
  aliased to a slugified `title`**, inline in the entity model (NO unpivot, NO
  runtime macro). Decisions:
  - Slug comes from `custom_fields.title` (e.g.
    `custom_100100000 as lunch_program`), sanitized to a valid identifier and
    deduped for collisions (~5/580 for students). Do NOT use the catalog `alias`
    column — it is the raw `custom_NNN` for ~87% of fields.
  - **Values are left encoded.** `select`/`multiple` (~255/580 for students)
    stay as stored codes; decoding via `custom_field_select_options` is a
    **deferred follow-up**. The other ~56% (`text`/`date`/`numeric`/`checkbox`
    Y-N/`file`) are already displayable.
  - **Scope = currently-populated** custom columns (≥1 non-null value) — profile
    per entity; re-scaffold as the rollout fills more fields.
  - The alias list + types are **generated once from the catalog + a non-null
    profile** and committed as static SQL/YAML (not a compile-time macro).
  - `source_class` → entity map: `SISStudent`→students, `FocusUser`→users,
    `SISSchool`→schools, `CoursePeriod`→course_periods, `CourseCatalog`→
    master_courses.
  - Excluded field types (not scalar values): `log` (→
    `custom_field_log_entries`), `computed`, `holder`, `signature`, `audio`,
    `file` ref columns as needed.
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
- **Soft-delete:** `deleted INT64` is **`NULL` for live rows and `1` for
  deleted** — there is no `0` (verified on `students`, `users`, `schools`,
  `address`, `student_enrollment_codes`, `custom_fields`). Filter
  `where deleted is null` (NOT `= 0`, which matches nothing). Applies to
  `address`, `schools`, `students`, `users`, `student_enrollment_codes`, and the
  `custom_field*` tables. Variants `inactive` / `active` / `archived` (STRING)
  on a few — confirm semantics per table.
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

## Execution runbook (resumable)

Any session resumes Phase B from here — no external memory needed.

1. Open #4213; pick the first unchecked **ungated** batch (gated = H, kipptaf —
   see waves below).
2. Gather inputs: this index (PK / soft-delete / curation / build context), the
   import-layout mapping (`.claude/scratch/focus-import-layout-mapping.md`) for
   wide-table curation, and `2026-06-18-focus-staging-attendance-lookups.md`
   (Batch C) as the staging template.
3. Extract columns: `INFORMATION_SCHEMA.COLUMNS` for the batch's tables
   (`column_name`, `data_type`, `ordinal_position`).
4. Write the plan via the **`superpowers:writing-plans`** skill (invoke it first
   — it sets the plan structure), using
   `docs/superpowers/plans/2026-06-18-focus-staging-<batch>.md` as the path and
   the Batch C plan as the concrete template (contract YAML per column; `unique`
   - `not_null` PK at `severity: error`; soft-delete filter where applicable;
     exclude `_dlt_*` + the audit-quad). Subagents do not auto-load skills — a
     dispatched plan-writer MUST be told to invoke `superpowers:writing-plans`
     before writing. Fill the `Plan doc` column in the table above.
5. Execute via `superpowers:subagent-driven-development`; open the PR
   (`Refs #4213`).
6. On merge: check the box in #4213.

## Gating waves

- **Wave 1 (parallel, no cross-batch deps):** staging for A, B, C (done), D, E,
  F, G, H, I, plus `int_focus__student_enrollment` (self-contained in B). H is
  now plain metadata staging (the unpivot was dropped), so it joins Wave 1.
  Custom values are inline-aliased within their entity batches (A, B, D, G).
- **Wave 2 (deferred follow-up):** decode the encoded `select`/`multiple` custom
  columns via `custom_field_select_options` (and reshape the `log`-type fields
  from `custom_field_log_entries`). Needs H's metadata staging.
- **Wave 3 (after district staging is merged + materialized in prod):** kipptaf
  region source + `stg_kippmiami__focus__*` wrappers (kipptaf source resolves to
  prod for `target=staging` CI).
