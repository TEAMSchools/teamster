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
- `rpt_gsheets__gradebook_audit_template` — the expectations upload template
  (write side; T&L exports it as the CSV they load into `U_EXPECTATIONS` via the
  PowerSchool plugin)

The upload-template spreadsheet carries two more models on the same exposure:
`rpt_gsheets__gradebook_audit_current_expectations` (the raw `U_EXPECTATIONS`
dump) and `rpt_gsheets__gradebook_audit_all_weeks` (the same week grid without
the expectations join, so it runs to the end of the year instead of stopping at
the last completed week). All four gsheets models publish as Connected Sheets
tabs — Dagster's exposure asset is a marker and writes nothing, so a new tab has
to be created by hand in the spreadsheet.
