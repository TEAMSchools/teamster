---
name: grad-plan-tracking
description: >-
  Use when any task touches Grad Plan Tracking: running or troubleshooting the
  PowerSchool Graduation Plan Progress Report Data Capture, refreshing the grad
  plan tracking sheet before a master-scheduling push, a school's tracker tab
  missing students, a row-cap check on the IMPORTRANGE Sources tabs, or work on
  gpprogress, gpnode, or rpt_gsheets__grad_plan_tracking. Triggers: grad plan
  tracking, grad plan tracker, graduation plan, credits missing to graduate,
  master schedule, gpprogress, gpnode, rpt_gsheets__grad_plan_tracking.
---

# Grad Plan Tracking

The family's reference doc is
[grad-plan-tracking-data-model.md](../../../docs/models/grad-plan-tracking-data-model.md).
Read its "What triggers it" and "Known issues, need to fix" sections before
running a refresh or explaining a missing row.

## Rules for every task

- **Newark and Camden only.** Paterson disables every grad-plan model
  (`int_powerschool__gpnode`, `int_powerschool__gpprogress_grades`, and the
  `gpprogresssubject*` staging models); Miami never ran PowerSchool grad plans.
  A Paterson or Miami request has no data to find — say so and point at the
  doc's "Decisions" section.
- **The dbt side needs no trigger of its own.**
  `rpt_gsheets__grad_plan_tracking` and its parents are views, so every read
  recomputes from whatever PowerSchool currently holds. The only "run" step is
  the PowerSchool Data Capture routine, plus the sheet extract refresh after it
  — see [refresh.md](references/refresh.md).
- Student-level progress and credit figures are PII (`config.meta.contains_pii`
  on `rpt_gsheets__grad_plan_tracking`). Any row you pull to diagnose a tab
  stays in the terminal and the session scratchpad; a commit, PR, or issue gets
  counts by school and tab only.
- Ashley Leonardi (Teaching and Learning) owns the policy questions — which
  diploma plans are tracked, when a refresh is needed. Anthony Walters (Data
  Team) owns the models and the sheet.

## Route by task

| Task                                                      | Read                                  |
| --------------------------------------------------------- | ------------------------------------- |
| Run the grad plan refresh before a master-scheduling push | [refresh.md](references/refresh.md)   |
| A tracker tab is missing students, or a tab looks capped  | [row-caps.md](references/row-caps.md) |
| Anything else that looks wrong (blank rows, wrong plan)   | The doc's "Known issues, need to fix" |

## Scripts

- [check_row_caps.py](scripts/check_row_caps.py): compares each Reports tracker
  tab's row cap against its source tab's row count (see
  [row-caps.md](references/row-caps.md)).
