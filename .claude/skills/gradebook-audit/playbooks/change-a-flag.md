# Add or remove a flag

## Procedure: Add a new flag

`stg_google_sheets__gradebook_flags` is disabled — no sheet step needed. Since
the July 2026 teacher/student split there are no UNPIVOT lists — every flag is a
hardcoded boolean column, and which model it lives in depends on its grain. Per
the split's design goal, do NOT add a "reason" column to a **student-level**
flag — those stay aggregated booleans, because they carry PII and fan out per
student. **Assignment-level** checks are the exception: `flag_reasons` on the
`category_summary` row already names them in plain language, so a new
assignment-level check needs a label added there (see "Add a new flag" below).

**Student-level flag** (per student × section × quarter, like
`qt_percent_grade_greater_100`/`qt_grade_70_comment_missing`):

1. Add the boolean column to `int_extracts__gradebook_audit_student_flags.sql`
   (in its main `select`, alongside the two existing `qt_*` flags) — the flag is
   computed once here, where both reports read it. Then add it to
   `rpt_gsheets__gradebook_audit_student_flags.sql`'s final filter
   (`where qt_percent_grade_greater_100 or qt_grade_70_comment_missing or <new_flag>`),
   and to that report's projected column list.
2. Add a matching `has_<flag>` boolean to `rpt_tableau__gradebook_audit.sql`'s
   `student_flags_aggregate` CTE (`countif(<new_flag>) > 0 as has_<flag>`) —
   this CTE reads `int_extracts__gradebook_audit_student_flags` — and thread it
   through `with_section_flags` (broadcast) and `health_calc` (both health
   columns, unless it's specifically excluded from one like
   `has_grade_below_70_no_comment` is from
   `is_healthy_gradebook_excl_comments`).
3. Update the properties YAML for all three models
   (`int_extracts__gradebook_audit_student_flags`,
   `rpt_gsheets__gradebook_audit_student_flags`,
   `rpt_tableau__gradebook_audit`).
4. Build in dependency order — `int_extracts__gradebook_audit_student_flags`
   first, then `rpt_gsheets__gradebook_audit_student_flags` and
   `rpt_tableau__gradebook_audit` (both read the int).

**Assignment-level check** (per assignment, like `percent_graded_min_not_met`):

1. Add the check to `int_powerschool__gradebook_assignment_scores_rollup.sql`
   and fold it into `assignment_has_flags`.
2. In `rpt_tableau__gradebook_audit.sql`'s `category_join`, add a window
   `countif` for it over the existing partition
   (`_dbt_source_project, sectionid, quarter, assignment_category_code`),
   matching its 4 siblings.
3. Add a plain-language label to the `array_to_string` array in
   `category_summary`, keeping the array order stable — Tableau groups on the
   string, so reordering changes existing values. Do NOT reword an existing
   label without telling the requester; the strings are user-facing.
4. Update the properties YAML for both models.

**Category-level flag** (per section × quarter × category, like
`not_enough_assignments`):

1. Add the boolean to `rpt_tableau__gradebook_audit.sql`'s `category_summary`
   CTE (populated on `category_summary` rows; null it on the `assignment_detail`
   branch of `combined`, matching the existing null-placeholder pattern).
2. Thread it into `health_calc`'s `logical_or(...)` for both health columns
   (unless deliberately excluded from one).
3. Update the properties YAML.
4. Build `rpt_tableau__gradebook_audit`.

Either way, verify the row-count floor is unaffected (still exactly 4
`category_summary` rows per section × quarter) and check
`is_healthy_gradebook_all_flags`/`_excl_comments` pick up the new flag
correctly.

## Procedure: Remove a flag

`stg_google_sheets__gradebook_flags` is disabled — no sheet step needed.

1. Remove the boolean column from wherever it's computed
   (`int_extracts__gradebook_audit_student_flags`'s main `select` for a
   student-level flag, `rpt_tableau__gradebook_audit`'s `category_summary` CTE
   for a category-level one).
2. Remove it from every place it's threaded through: the gsheets model's final
   filter and projected columns (if student-level), `student_flags_aggregate` /
   `with_section_flags` (if student-level), and both `health_calc`
   `logical_or(...)` expressions.
3. Update the properties YAML for the affected model(s).
4. Build the modified models.
