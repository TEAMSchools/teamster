# Data model: lineage, sources, and thresholds

## Procedure: Explain the data model

Read the reference doc and answer from it. For AY 2026-2027 changes, also read
the spec doc.

## Configurable thresholds

These values are hardcoded in SQL. When the user asks to change a threshold,
find the location below and update the literal.

| Threshold                                                                                                                                            | Current value | Location                                                                                |
| ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | --------------------------------------------------------------------------------------- |
| `min_graded_percent` — minimum fraction of expected assignments that must be scored for an assignment to pass the `percent_graded_min_not_met` check | `0.90` (90%)  | `invalid_assign_check` CTE in `int_powerschool__gradebook_assignment_scores_rollup.sql` |

To change `min_graded_percent`: update the literal `0.90` in the
`invalid_assign_check` CTE (`if(assign_percent_graded < 0.90, true, false)`).

The other policy literals in the same model's `flags` CTE: the 10-point maximum
for W/H/F (`assign_max_score_not_10`, `totalpointvalue != 10`) and the
half-class exemption bar (`overly_exempt_assignment`,
`.5 * n_students <= n_exempt`). The per-student scoring rules (a missing W/H/F
scores 5 in MS, a missing assignment scores 0 in HS, a Summative scores at least
half its points) live in the package model
`src/dbt/powerschool/models/sis/intermediate/int_powerschool__gradebook_assignments_scores.sql`,
which builds in each district.

The staff-facing statement of these rules for AY 2026-2027 is the
[SY 27 Gradebook Health Checklists](https://docs.google.com/document/d/1j_D9uJki4AuJP0yijuVVYaJkvgCJB8tgINgLcF-YEJ8/edit)
doc, one tab each for MS and HS, and it matches the assignment checks rule for
rule. Read it with the Google Docs connector. Quote it when telling a teacher
which rule a score breaks, and check its sharing before linking it in a reply.

The grading policy also sets a 200-point quarterly total for Summative. No check
enforces it, and Summative has no per-assignment maximum. If asked whether the
audit catches an over- or under-weighted Summative quarter, the answer is no;
adding it is a new category-level flag (`../playbooks/change-a-flag.md`).

## Sumner: where the MS override is matched

KIPP Sumner Academy (`schoolid = 179905`) is an ES in PowerSchool whose grades 5
and 6 are audited as MS from AY 2025 on. The override is matched in several
places, by different keys:

- `base_powerschool__sections` (package): `schoolid = 179905` and
  `grade_level >= 5` sets `school_level_alt = 'MS'`, which reaches the audit
  through sections and course enrollments.
- `int_extracts__student_enrollments`: `school_abbreviation = 'Sumner'`.
- `int_students__school_directory`: `school_short_name = 'Sumner'` (what the
  template and all-weeks models join for `school_level_alt`).
- `stg_powerschool__schools` (package): `abbreviation = 'Sumner'` makes the base
  level ES.

Never match on school name: PowerSchool has renamed Sumner before. A change to
the override touches every place above.

## Changing `section_or_period`

The dashboard groups section rows on this label, so it must stay unique per
teacher, course and quarter. `int_extracts__course_schedule_by_term` has an
`error`-severity uniqueness test on it; the second copy in
`int_extracts__course_enrollments_by_term` has none. After editing either,
re-run the collision query in
[#5379](https://github.com/TEAMSchools/teamster/issues/5379) against both. The
workbook's section worksheets (`Your sections grid`, `Your sections flags`,
`Teacher sections panel`, `Sheet Card - shortfalls`) and its action filters and
tooltips all slice on this label, so a non-unique label sums two sections into
one row with no error.

## Procedure: List refs, lineage, or sources for the gradebook audit dashboard

Do NOT search the codebase. Go directly to the exposure file:

`src/dbt/kipptaf/models/exposures/tableau.yml`

Find the exposure named `academic_gradebook_health_suite` and read its
`depends_on` list — that is the authoritative answer. It is the live dashboard
staff actually use, and it reads 4 models besides the audit, so the audit is one
input among several rather than the whole exposure.

Current `depends_on` list (update if the exposure changes):

- `rpt_tableau__gpa_goals`
- `rpt_tableau__gpa_goal_progress`
- `rpt_tableau__gpa_cumulative_year`
- `rpt_tableau__student_course_grades`
- `rpt_tableau__gradebook_audit`

Two disabled exposures, `gradebook_audit` and `gradebook_audit_teacher_report`,
also name `rpt_tableau__gradebook_audit`. Do NOT read either as the answer —
`gradebook_audit`'s workbook holds one sheet, has no views, and reads an extract
from a dbt Cloud CI schema that no longer exists. Mention them only if the user
asks about disabled or archived workbooks.

Two companion Google Sheets have their own exposures in
`src/dbt/kipptaf/models/exposures/google-sheets.yml` — check there if asked
about the gsheets side rather than the Tableau side:

- `rpt_gsheets__gradebook_audit_student_flags` — the flagged-student review
  sheet (read side, carries student PII)
- `rpt_gsheets__gradebook_audit_template` — the loaded expectations joined to
  the calendar, one row per week with W/H/F/S columns (upload side). It
  inner-joins `U_EXPECTATIONS` and stops at the last completed week, so it shows
  only weeks already loaded; the end-user skill uses it as a cross-check and an
  emergency restore source, not as the grid a new load is built from

The upload-template spreadsheet carries two more models on the same exposure:
`rpt_gsheets__gradebook_audit_current_expectations` (the raw `U_EXPECTATIONS`
dump) and `rpt_gsheets__gradebook_audit_all_weeks` (the week grid without the
expectations join, so it runs to the end of the year; it also drops Miami and ES
explicitly). `all_weeks` is the grid the end-user skill matches a new load
against. All four gsheets models publish as Connected Sheets tabs — Dagster's
exposure asset is a marker and writes nothing, so a new tab has to be created by
hand in the spreadsheet.
