# Gradebook Audit AY 2026-2027 Design

## Background

The gradebook audit Tableau dashboard helps school leaders and instructional
coaches audit teacher gradebooks for compliance with KIPP TAF grading policy. It
is powered by `rpt_tableau__gradebook_audit` and covers the current academic
year only, organized by calendar week within each quarter.

Full pipeline reference:
[`docs/reference/gradebook-audit-data-model.md`](../reference/gradebook-audit-data-model.md)

## Current coverage (AY 2025-2026)

| Region   | School level | Coverage                                    |
| -------- | ------------ | ------------------------------------------- |
| Camden   | MS, HS       | Full audit                                  |
| Camden   | ES           | EOQ comments only (`qt_es_comment_missing`) |
| Newark   | MS, HS       | Full audit                                  |
| Newark   | ES           | EOQ comments only (`qt_es_comment_missing`) |
| Miami    | ES, MS       | Full audit — **removing AY 2026-2027**      |
| Paterson | n/a          | Not on dashboard — **adding AY 2026-2027**  |

## AY 2026-2027 changes

### Remove Miami

Miami ES and MS are migrating to Focus gradebook and will be removed from this
dashboard entirely. All Miami-specific SQL branches become dead code once Miami
rows are removed from the config sheets.

### Add Paterson

Paterson joins the dashboard for AY 2026-2027.

**Paterson MS:** same flags and expectations as Newark MS.

**Paterson ES:** EOQ comments only — `qt_es_comment_missing` flag only, same
pattern as Camden ES and Newark ES.

**Paterson HS:** no HS schools in Paterson, no rows needed.

**Expectations source:** Paterson MS expectations will use the Google Sheet
(copying Newark MS values) until PS instance access is available to deploy the
U_EXPECTATIONS plugin. Once deployed, migrate to the PS-native source following
the same pattern as PR #4077 (Camden integration).

### Remove FYI flags

Three flags are excluded from the Tableau health score via a calculated field
but still generate rows in the extract. Remove them from SQL and config:

- `w_grade_inflation`
- `assign_s_hs_score_not_conversion_chart_options`
- `assign_s_ms_score_not_conversion_chart_options`

(`qt_teacher_s_total_less_200` is also a FYI flag but handled under Summative
200 removal below. `qt_student_is_ada_80_plus_gpa_less_2` is being moved to
`rpt_tableau__gradebook_gpa` separately.)

### Remove Summative 200 point-value flags

Remove `qt_teacher_s_total_greater_200` and `qt_teacher_s_total_less_200` from
`int_tableau__gradebook_audit_categories_teacher` and all downstream models.
Currently active for Camden and Newark. The Miami 100-pt variants
(`qt_teacher_s_total_greater_100`, `qt_teacher_s_total_less_100`) are removed as
part of the Miami dead-code cleanup.

### 7-day grace period for percent-graded flags

`w/h/f/s_percent_graded_min_not_met` should only fire for assignments that have
been due for at least 7 days. Change: in
`int_tableau__gradebook_audit_categories_teacher`, wrap the `n_expected` and
`n_expected_scored` window sums with a conditional on
`a.duedate <= current_date - 7 days`.

### Remove the exceptions mechanism

T&L has decided to eliminate the suppression table
(`stg_google_sheets__gradebook_exceptions`) entirely. Remove the model, its
source entry, and all 15+ LEFT JOINs to it across five intermediate models. This
is the largest single simplification in scope.

### Move EOQ suppression to Tableau (future)

`is_quarter_end_date_range` is already present in the extract output. Tableau
will use it to filter EOQ items outside the window. No dbt exception joins
needed once the exceptions table is removed. No additional dbt changes required
for this — it is a Tableau workbook change.

## Out of scope for this implementation

### QTD cumulative assignment count

Change `w/h/f/s_expected_assign_count_not_met` from a weekly check to a
quarter-to-date cumulative check. Blocked on open format question: should
`stg_google_sheets__gradebook_expectations_assignments` store cumulative targets
per week, or keep per-week values and sum in SQL?

### Anchor-row / "in the clear" redesign

Replace the current design (one row per possible flag slot, `flag_value = 0` for
non-fired flags) with a leaner pattern: rows for active flags only plus one
anchor row per teacher per class. Required for the school-level summary view
(percentage of classrooms with at least one active flag). Needs a separate spec
and plan.

### PS-native expectations source migration

`stg_powerschool__u_expectations` exists for Newark. Camden has the plugin
deployed (PR #4077 pending full integration). Paterson pending PS instance
access. Full migration — union across regions, inject `academic_year`, unpivot —
deferred until all regions have the plugin deployed.

## Open questions

**QTD expectations format:** If staying on Google Sheets, store cumulative or
per-week values? If moving to PS plugin, confirm whether the plugin stores
per-week or cumulative values. Resolving this unblocks the QTD cumulative
assignment count change.
