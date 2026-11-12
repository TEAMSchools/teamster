# DDI goals

Where a goal on the DDI Suite comes from, and how to change one. Column
semantics: the reference doc's `rpt_tableau__ddi_dashboard` section.

## Where the number comes from

The DDI Suite's grade, school and region goals are `grade_goal_differentiated`,
`school_goal_differentiated` and `region_goal_differentiated` on
`rpt_tableau__ddi_dashboard`. The workbook's goal calcs read these columns
unchanged; no goal logic lives in the workbook. Each column takes the first of:

1. A fixed `Goal` from a matching row on the Module Goal Rules tab of the
   Assessments spreadsheet (`int_assessments__module_goal_rules`).
2. On QA and CRQ modules, the Academic Goals tab's `QA Goal` column, where
   filled.
3. The plain lookup goal (`grade_goal`, `school_goal`, `region_goal` from the
   Academic Goals tab) plus a matching rule's `Goal Offset`, or plus 0.

A rule matches on region, module type, grade (`Grade Min` to `Grade Max`
inclusive, 0 is kindergarten) and discipline. A blank `Discipline` matches every
subject; a named one matches the subjects the course subject crosswalk maps to
it.

## Changing a goal

A goal change is a sheet edit, never a model or workbook edit:

- A per-grade or per-school target: the Academic Goals tab (`QA Goal` for QA and
  CRQ modules).
- A rule for a module type (a fixed goal, or the lookup goal plus an offset):
  the Module Goal Rules tab. Fill exactly one of `Goal` and `Goal Offset`, as a
  decimal (0.8, not 80).
- When an existing rule already has the right goal, widen its grade range
  instead of adding a row. A new row overlaps an existing rule when region and
  module type match, the grade ranges share a grade, and the disciplines match
  or either is blank: a 3-3 row overlaps a 3-8 rule, a 9-9 row does not overlap
  a 10-12 rule. Every overlapping rule is dropped, so the rows they covered fall
  back to steps 2 and 3 above. To change part of a rule's range, split it into
  rows that share no grade.
- Rules carry no academic year. An edit changes every year the dashboard shows,
  past years included.
- Hand the edited tab over per the SKILL.md _Sheet handoff_.

A malformed or overlapping rule fails a warn test on
`stg_google_sheets__assessments__module_goal_rules` (the overlap test is the
singular `stg_google_sheets__assessments__module_goal_rules__overlap`), and its
description names the cell to fix. A failing one means that rule is not applied.
A sheet edit rebuilds the staging model on its own; the dashboard shows the
change after the next DDI Suite extract refresh (the `ddi_suite` exposure's
`cron_schedule`).
