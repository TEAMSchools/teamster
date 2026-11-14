# Academic Health: grades and GPA side of the suite

The Academic & Gradebook Health Suite reads the gradebook audit and four grades
and GPA models. This file routes work on the GPA side. The authoritative source
is the reference page,
[`docs/models/academic-health-data-model.md`](../../../../docs/models/academic-health-data-model.md);
read the section named below before answering.

Anthony Walters built and owns both suites' dashboards. The old Gradebook and
GPA Dashboard no longer refreshes; retiring it is his call, not a cleanup to
propose.

## Routing

| Task                                                        | Reference page section                                  |
| ----------------------------------------------------------- | ------------------------------------------------------- |
| Which model feeds which view                                | _Dashboard models_                                      |
| What a GPA term means (term, Y1, cumulative, weighted)      | _Terms_                                                 |
| Enter or change GPA goals                                   | _Process: the GPA goals sheet_                          |
| A goal line is missing or a goal test fails                 | _Process: the GPA goals sheet_, step 3 (the four tests) |
| Start-of-year work: goals, grading policy, scales, rollover | _Yearly upkeep_                                         |
| A number looks wrong                                        | _Known issues, need to fix_ first                       |
| Why the model does something that looks odd                 | _Decisions_                                             |

## Before changing a GPA model

- Unweighted is the default. Every goal and band uses unweighted GPA; weighted
  appears only where the view says so.
- A new weighted grade scale needs its unweighted twin mapped twice: by name in
  `stg_powerschool__storedgrades` and by id in `base_powerschool__sections`.
  Missing either makes unweighted equal weighted, with no error (#5563).
- Cumulative GPA is per school, not per student. Do not collapse it.
- The goal comparison is `>=` in the dashboard; the sheet's `direction` column
  does not reach it.
- Miami is out of the goal population until #5171.

## Open bugs

- #5562: past-year cumulative goal rates use today's GPA.
- #5564: the Y1 `F*` label compares a 0-100 percent with 0.5.

Fix these in their own PRs. Do not reword the reference page to describe the bug
as intended behavior.

## After a change

Update the reference page section you used, and this file only if a route or
rule above changed.
