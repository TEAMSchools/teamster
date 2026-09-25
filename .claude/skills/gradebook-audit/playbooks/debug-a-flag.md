# Procedure: Debug a flag that isn't firing

Ask: which flag, region, school level, and quarter.

First establish which flag: `has_grade_above_100` /
`has_grade_below_70_no_comment` (student-level, aggregated from
`int_extracts__gradebook_audit_student_flags`), `not_enough_assignments`
(category-level), or one of the two health columns
(`is_healthy_gradebook_all_flags` / `is_healthy_gradebook_excl_comments`).

Check in order:

1. **Boolean `true` at its source?** Student-level: query
   `int_extracts__gradebook_audit_student_flags` directly for the
   student/section/quarter — it is unfiltered (one row per scoped enrollment,
   flag `true` or `false`), so it shows whether the grade/comment computation
   fired. (`rpt_gsheets__gradebook_audit_student_flags` is the same rows
   filtered to flagged-only, so absence there just means no flag fired.)
   Category-level: query `rpt_tableau__gradebook_audit` filtered to
   `row_type = 'category_summary'` for the section/quarter/category.
2. **In scope at all?** Four silent exclusion rules apply in `category_join`'s
   `WHERE` (`rpt_tableau__gradebook_audit`) and matched in
   `int_extracts__gradebook_audit_student_flags`'s own filters:
   - `_dbt_source_project != 'kippmiami'` — Miami is excluded at source (AY
     2026-2027 onward)
   - `school_level_alt != 'ES'` — ES is excluded everywhere; ES is handled
     separately by `rpt_tableau__gradebook_es_comments`
   - `exclude_from_gpa = 0` — drops Lunch, Early Dismissal and Study Hall, which
     carry `excludefromgpa = 1` in PowerSchool
   - `course_number != 'SEM22106G1'` — KIPP Newark Lab's Advisory; graded, but
     no course-level expectation grain exists (see the reference doc's
     _Course-level scope_). A Lab teacher who teaches only advisory has no rows
     in either model at all
3. **For a student-level flag, did it survive the aggregation into
   `rpt_tableau__gradebook_audit`?** `student_flags_aggregate` groups
   `int_extracts__gradebook_audit_student_flags` to
   `_dbt_source_project, sectionid, quarter` — if the flagged row exists in the
   int but `has_<flag>` still reads `false` on the teacher-side report, check
   the join in `with_section_flags` (on
   `_dbt_source_project, sectionid, quarter`) for a key mismatch, not the flag
   logic itself.
4. **Row-count floor intact?** Every section × quarter should have exactly 4
   `category_summary` rows (one per W/H/F/S). If fewer, the
   `int_powerschool__u_expectations_qtd_unpivot` join in `category_join` is
   probably missing a category for that region/school_level/quarter — check that
   model directly, not the flag logic.
5. **Is the affected student/course/quarter one of the known ambiguous-dedup
   cases in `int_extracts__course_enrollments_by_term`?** (Inherited by
   `int_extracts__gradebook_audit_student_flags`, which reads it — and thus by
   both reports downstream.) Its `enrollments` CTE picks one section per
   student/course/quarter with a `row_number()` tiebreaker that is frequently a
   true tie (see reference doc) — when it is, the teacher/section actually in
   scope for that student that quarter is arbitrary and can differ from what
   you'd expect from PowerSchool. Query the model directly for that
   student/course/quarter to check whether more than one candidate section
   exists before assuming the flag logic itself is wrong.

`stg_google_sheets__gradebook_flags` is disabled — do not check the allowlist
sheet. `stg_google_sheets__gradebook_exceptions` is also disabled — do not check
for exception rows.
