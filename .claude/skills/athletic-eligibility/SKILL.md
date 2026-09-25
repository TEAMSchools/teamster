---
name: athletic-eligibility
description: >-
  Use when any task touches the athletic eligibility tracker: the student
  athlete eligibility policy changed or needs its yearly check, a region wants
  different high school ADA weighting, a student's eligibility status looks
  wrong or blank, or work on int_students__athletic_eligibility,
  rpt_gsheets__athletic_eligibility, or the statuses that
  rpt_deanslist__promo_status unpivots.
---

# Athletic eligibility

The tracker's reference doc is
[athletic-eligibility-data-model.md](../../../docs/models/athletic-eligibility-data-model.md).
Read its "Steps" section (stop at "Outputs") before changing any rule.

## Rules for every task

- Each quarter's status is one `case` that stops at the first match. High school
  branches come before middle school branches, and the middle school branches
  are limited by grade range so a high schooler cannot match them. A new branch
  goes in the right band's block, never at the end.
- Q1 reads last year's weighted ADA for high school and unweighted ADA for
  middle school. Q2 through Q4 high school rules read weighted ADA.
- The policy doc has a Reporting tab that turns the policy into statuses. Where
  it is more specific than the policy text, the tracker follows the Reporting
  tab.
- Statuses and the inputs behind them are student-level PII. Student lists go to
  a tab-separated file in the session scratchpad; commits and PRs get counts by
  school and status only.
- Before any status-changing PR merges, tell the user how many students lose
  eligibility (move to an Ineligible status from Eligible or Probation), so
  Teaching and Learning can be warned.

## Route by task

| Task                                                  | Read                                            |
| ----------------------------------------------------- | ----------------------------------------------- |
| The policy changed, or the yearly policy-vs-SQL check | [policy-change.md](references/policy-change.md) |
| A region wants different high school ADA weighting    | [policy-change.md](references/policy-change.md) |
| A student's status looks wrong                        | The table and query below                       |

## Why did this status come out this way

| Status seen                                    | Most likely cause                                                          |
| ---------------------------------------------- | -------------------------------------------------------------------------- |
| Blank Q1                                       | No previous-year GPA or ADA: the student is new to the network             |
| Blank Q2 to Q4 for a high schooler             | A missing high school input sent the row to rules that also found nothing  |
| Ineligible - Age                               | 19th birthday before September 1 of the academic year                      |
| Ineligible - Credits in Q3 or Q4               | A failing Y1 grade as of Q2, not the 30-credit count                       |
| A middle school status the sheet can't explain | It reads the running ADA and current Y1 GPA, which the sheet does not show |

To see which input decided one student's status, read their row (the result is
PII: terminal only). Match the non-null inputs against the doc's "Steps" tables;
a pattern the table does not explain is in its "Known issues".

```sql
select
    grade_level, grade_level_prev, is_first_time_ninth, is_age_eligible,
    met_py_credits, met_cy_credits, py_y1_gpa, cy_q1_gpa, cy_s1_gpa, cy_y1_gpa,
    py_y1_unweighted_ada, py_y1_weighted_ada, cy_weighted_term_q1,
    cy_weighted_s1_ada, `ada`,
    q1_ae_status, q2_ae_status, q3_ae_status, q4_ae_status,
from `teamster-332318.kipptaf_students.int_students__athletic_eligibility`
where student_number = <student_number>
```

## Scripts

- [status_diff.py](scripts/status_diff.py): compare a compiled branch build of
  the model to prod, by status transition, and write the student-level list to
  scratch.
