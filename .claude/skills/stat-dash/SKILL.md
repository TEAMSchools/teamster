---
name: stat-dash
description: >-
  Use when any question or task touches the State Testing Analysis Tool (STAT)
  dashboard or its lineage. Triggers: the "stat dash" or state assessment
  dashboard, entering or bootstrapping state/city/neighborhood comparison
  figures into the comps sheet, a comparison reading false or a comp not
  appearing, a student's state assessment score missing from the dashboard, the
  Pearson-to-Cambium NJ vendor migration, the student crosswalk sheet, or
  working on rpt_tableau__state_assessments_dashboard,
  rpt_tableau__state_assessments_dashboard_comps,
  int_tableau__state_assessments_demographic_comps,
  stg_google_sheets__state_test_comparison_demographics,
  stg_google_sheets__pearson__student_crosswalk, int_pearson__all_assessments or
  stg_cambium__njgpa and their upstream models.
---

# STAT Dashboard

## Always read first

- Reference doc:
  [`docs/models/stat-dashboard-data-model.md`](../../../docs/models/stat-dashboard-data-model.md)

It is authoritative for lineage, the dual-vendor union, the two comps paths, the
controlled vocabulary, and the open issues. Read it before answering anything,
not just before editing.

**Three facts that cause most of the wrong answers here:**

- `academic_year` is the STARTING year of the school year. Testing happens in
  the spring, so a source reporting "2026 results" means the 2025-2026 school
  year, which is `academic_year = 2025`. The published label always runs one
  ahead of the warehouse value. Confirm before generating any row.
- **There are two comps calculations, not one.** The `state_comps` CTE inside
  `rpt_tableau__state_assessments_dashboard` and the separate
  `rpt_tableau__state_assessments_dashboard_comps` read different things. A
  number that differs between Overview and Advanced Comps is usually that, not a
  bug. See the reference doc.
- `int_pearson__all_assessments` carries **both** Pearson and Cambium. Its name
  is a known misnomer. Never assume a row in it is Pearson.
- **The vendor changed on a date, not per assessment.** Through December 2025 it
  is Pearson; Spring 2026 and everything after is Cambium, for all NJ state
  testing. So the Pearson relations are history and will not gain rows -- a gap
  in one cannot be fixed by a re-pull -- and `stg_pearson__njgpa` is moot.

---

## Before changing this pipeline

Confirm with the requester the grain, region, academic year, and expected effect
on the dashboard (more rows, different booleans, changed labels, or none for a
refactor). Then state these model-specific risks before implementing:

- **Which of the two comps paths does this touch?** Changing the sheet touches
  both. Changing `rpt_tableau__state_assessments_dashboard_comps` touches only
  Advanced Comps.
- **Does it move a string the ten-column self-join keys on?** If so, rows
  silently lose their Region partner and read `false`, not null.
- **PII.** Student-level rows live in `rpt_tableau__state_assessments_dashboard`
  and in the failure rows of `test_incorrect_student_number_pearson`, which
  carry student names. Never paste them outbound.
- Contract enforcement on both `rpt_` models and both staging models.

Validate with the audit query from the relevant procedure below.

---

## Procedure: List refs, lineage, or sources

Do not search the codebase. Read the exposure `state_testing_analysis_tool` in
`src/dbt/kipptaf/models/exposures/tableau.yml` and report its `depends_on`:

- `rpt_tableau__state_assessments_dashboard`
- `rpt_tableau__state_assessments_dashboard_comps`

For which of the six Tableau views reads which of those two, use the table in
the reference doc. `rpt_tableau__state_testing_accomodations` is a **different**
workbook — do not pull it in.

---

## Gotchas

- **Never judge the current contents of either Google Sheet from the prod `stg_`
  table.** Both are frozen at the last prod build. Read the `src_` external live
  instead (Step 6).
- **The Tableau MCP cannot answer "what does the workbook do with this field".**
  It is read-only, returns no calculated-field text, and 500s on
  `get-datasource-metadata` for the embedded extracts this workbook uses. Use
  the `tableau-workbook-xml` skill to download and inspect the `.twb`.
- **`rpt_tableau__state_testing_accomodations` is not part of this dashboard.**
  Similar name, different workbook.
- **Cambium and Pearson aligned columns are maintained in two separate
  packages** and cannot share code. Changing a band, label, or mapping in one
  means changing it in the other. See the reference doc.
