---
name: hs-early-warning
description: >-
  Use when any question or task touches the High School Early Warning dashboard
  or its lineage. Triggers: the On Track 9th, Early Warning, Graduation
  Eligibility or Community Service tabs; an early warning flag (chronically
  absent, below 2.0 GPA, core Fs, over age, on track for promotion) looking
  wrong; a high school missing from the dashboard; community service hours or
  the 50-hour graduation goal; DeansList community service custom fields
  (9th_hours to 12th_hours) or last year's hours disappearing; the start-of-year
  rollover for the high schools; or working on
  rpt_tableau__hs_early_warning_dashboard, rpt_tableau__community_service,
  rpt_tableau__graduation_requirements,
  int_deanslist__students__custom_fields__pivot or
  rpt_gsheets__community_service_upload.
---

# High School Early Warning

The dashboard answers whether a high school student is on track to graduate,
from three independent extracts. The reference doc is the manual:
[`docs/models/hs-early-warning-data-model.md`](../../../docs/models/hs-early-warning-data-model.md).

## Rules for every task

- Every threshold on the dashboard is a Tableau calculation over the three
  extracts, not dbt logic. The doc writes them out. Opening the workbook through
  the Tableau MCP or `tableau-workbook-xml` costs a lot of tokens: ask the user
  first, and reproduce a flag from the extract through BigQuery before reaching
  for the workbook.
- Miami is out of scope for graduation pathways
  (`rpt_tableau__graduation_requirements` filters `region != 'Miami'`). The
  early warning and community service extracts have no region filter. Miami Tech
  is on Community Service but not on Early Warning, because it has no reporting
  term rows (see `early-warning.md`).
- The extracts are student-level PII. Rows stay in the terminal and the session
  scratchpad; commits, PRs and docs get aggregates without small cells.
- Walters owns the family (from 2026-09-30).

## Route by task

| Task                                                                                  | Read                                                                                                             |
| ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Early warning flags, On Track, grades, GPA, credits, suspensions, a school missing    | [references/early-warning.md](references/early-warning.md)                                                       |
| Community service hours, the 50-hour goal, DeansList custom fields, the yearly upload | [references/community-service.md](references/community-service.md)                                               |
| Start-of-year rollover for the high schools                                           | [references/yearly-upkeep.md](references/yearly-upkeep.md)                                                       |
| Pathway codes, cut scores, NJGPA, transfer scores, the PowerSchool write-back         | [../graduation-pathways/SKILL.md](../graduation-pathways/SKILL.md)                                               |
| NJDOE portfolio appeal PDFs                                                           | [../graduation-pathways/references/portfolio-appeals.md](../graduation-pathways/references/portfolio-appeals.md) |

## Why did this number change

| Symptom                                          | First check                                                                                                                               |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| A whole high school vanished from Early Warning  | Its `RT` rows in `stg_google_sheets__reporting__terms` for the current year (INNER join); in August or September, also `yearly-upkeep.md` |
| Last year's service hours dropped to zero        | The DeansList custom fields; see `community-service.md` → The yearly upload                                                               |
| A student's service hours dropped                | A new DeansList behavior name that does not start with a number                                                                           |
| On-track percentages disagree between two people | Which `On Track Indicator` parameter each had selected                                                                                    |
| Landing page shows almost no NJGPA (`S`)         | Missing cut score rows; `graduation-pathways` → RUNBOOK: new cut scores                                                                   |
| A student shows twice on Graduation Eligibility  | Two College and Career course enrollments; known issue in the doc                                                                         |

## Scripts

None of its own. The portfolio appeal converter lives in
`../graduation-pathways/scripts/portfolio_appeals_to_tsv.py`.
