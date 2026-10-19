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
  stg_google_sheets__pearson__student_crosswalk,
  int_assessments__state_nj_scores, int_cambium__all_assessments or
  stg_cambium__njgpa and their upstream models.
---

# STAT Dashboard

## Always read first

Read
[`docs/models/stat-dashboard-data-model.md`](../../../docs/models/stat-dashboard-data-model.md)
from the top through _Terms_, stopping at `## Where the data comes from`, before
answering anything. The doc is long: list its headings first with
`rg -n '^#{2,4} ' docs/models/stat-dashboard-data-model.md` and pass `offset`
and `limit` so the Read stops at the named heading. Then read the section the
route below names the same way. The doc is authoritative for lineage, the
dual-vendor union, the two comps paths, the controlled vocabulary, decisions and
open issues.

Four facts that cause most of the wrong answers here:

- `academic_year` is the starting year of the school year. A source reporting
  "2026 results" means `academic_year = 2025`. The published label always runs
  one ahead. Confirm before generating any row.
- There are two comps calculations. The `state_comps` CTE inside
  `rpt_tableau__state_assessments_dashboard` and the separate
  `rpt_tableau__state_assessments_dashboard_comps` read different things. A
  number that differs between Overview and Advanced Comps is usually that, not a
  bug.
- `int_assessments__state_nj_scores` carries both Pearson and Cambium, under
  neutral column names. Never assume a row in it is Pearson.
- The NJ vendor changed on a date, not per assessment: Pearson through December
  2025, Cambium from Spring 2026 for all NJ state testing. The Pearson relations
  are history; a gap in one cannot be fixed by a re-pull.

## Rules for every task

- Lineage: do not search the codebase. Read the exposure
  `state_testing_analysis_tool` in
  `src/dbt/kipptaf/models/exposures/tableau.yml`; it depends on
  `rpt_tableau__state_assessments_dashboard` and
  `rpt_tableau__state_assessments_dashboard_comps`. NJ and Florida official
  scores both reach the dashboard through `int_assessments__state_scores`, whose
  NJ leg is `int_assessments__state_nj_scores`. Both reporting models also read
  `int_assessments__state_nj_scores` directly, only to gate the preliminary
  branch. `rpt_tableau__state_testing_accomodations` is a different workbook.
- PII. Student-level rows live in `rpt_tableau__state_assessments_dashboard` and
  in the failure rows of `test_incorrect_student_number_pearson`, which carry
  student names. Quote UUIDs and counts only, outside the terminal.
- Before changing the pipeline, confirm with the requester the grain, region,
  academic year and expected effect on the dashboard (more rows, different
  booleans, changed labels, or none for a refactor). Then state:
  - which comps path it touches: the sheet feeds both; the comps model feeds
    only Advanced Comps;
  - whether it moves a string or value on one of the nine columns the comps
    model's Region self-join keys on. A row that loses its partner reads
    `false`, not null;
  - that both `rpt_` models and both sheet staging models are contract-enforced.

## Route by task

Read the one file for your task.

| Task                                                                    | Read                                                                                                                            |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| A student's score is missing, or attached to the wrong student          | [references/crosswalk.md](references/crosswalk.md)                                                                              |
| The detector has a batch outstanding; generate or audit crosswalk rows  | [references/crosswalk.md](references/crosswalk.md)                                                                              |
| After a Cambium load; a roster bar is part-colored; a grain test failed | [references/after-a-load.md](references/after-a-load.md)                                                                        |
| Enter interim comps from a screenshot, deck or press figure             | [references/comps-sheet.md](references/comps-sheet.md)                                                                          |
| Load a year's official comps (NJDOE files, FLDOE downloads)             | [references/state-comps-files.md](references/state-comps-files.md)                                                              |
| Replace interim comps with the official file                            | [references/state-comps-files.md](references/state-comps-files.md), then [references/comps-sheet.md](references/comps-sheet.md) |
| A comparison reads `false`, or a comp is missing                        | [references/comps-debugging.md](references/comps-debugging.md)                                                                  |
| Verify a comps-model change against production                          | [references/comps-debugging.md](references/comps-debugging.md)                                                                  |
| July rollover, or spring preliminary scores                             | [references/rollover.md](references/rollover.md)                                                                                |
| Two views show different comp numbers for the same test                 | doc _The two comps paths_ (under _How the models work_), stop at `## Supporting models`                                         |
| Which view reads what, or what a view shows                             | doc _Dashboard outline_, stop at `## How the models work`                                                                       |
| How a model works, or a change to the NJ vendor mapping                 | doc _How the models work_ and _Supporting models_, stop at `## Inputs`; then _Decisions_ before proposing any redesign          |

## Gotchas

- Never judge the current contents of either Google Sheet from the prod `stg_`
  table; both are frozen at the last build. Read the `src_` external live
  through ADC from Python (the BigQuery MCP has no Drive scope).
- The Tableau MCP cannot say what the workbook does with a field: it returns no
  calculated-field text and errors on this workbook's embedded extracts. Use the
  `tableau-workbook-xml` skill to read the `.twb`.
- The race, ML and IEP mappings are written twice: in the pearson package's
  `int_pearson__all_assessments` and in the cambium package's
  `int_cambium__all_assessments`. The Pearson side is frozen, so a change there
  means matching it in the Cambium model.
- The exposure has no `cron_schedule`; Tableau Server refreshes the extracts, so
  a model change shows nothing until that refresh.

## Scripts

- [scripts/audit_crosswalk.py](scripts/audit_crosswalk.py): replays every
  crosswalk sheet row through the compiled tiered matcher and prints counts;
  exits 1 on any disagreement. Procedure in
  [references/crosswalk.md](references/crosswalk.md).
- [scripts/build_nj_comps.py](scripts/build_nj_comps.py) and
  [scripts/build_fl_comps.py](scripts/build_fl_comps.py): build a year's comps
  sheet rows from the NJDOE and FLDOE files. Procedure in
  [references/state-comps-files.md](references/state-comps-files.md).
