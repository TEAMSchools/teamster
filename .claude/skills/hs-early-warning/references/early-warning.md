# Early warning extract

`rpt_tableau__hs_early_warning_dashboard` feeds the On Track 9th and Early
Warning tabs. This file is enough to diagnose a missing school or a grain
problem. Open the doc's _The five early warning flags_ only for a question about
a flag's threshold.

## Grain and scope

One row per student, reporting term and course, tested by
`unique_combination_of_columns` on `student_number`, `reporting_term`,
`course_number`. A student with no stored grade for a term still gets one row
with a null course.

Scope comes from `int_extracts__student_enrollments`: the current academic year,
`rn_year = 1`, `school_level = 'HS'`, `is_enrolled_recent`. Terms come from
`stg_google_sheets__reporting__terms` with `type = 'RT'`, excluding
`Summer School` and `Y1`, through an INNER join on academic year and school.

Two consequences of that INNER join:

- A school with no `RT` rows for the year is absent, with no error. Check the
  terms sheet before any SQL when a school goes missing. The sheet keys schools
  by PowerSchool `school_id`; the extract's `school` column holds the short name
  people use (NCA, NLH, KHS), and `schoolid` the id.
- Miami Tech is absent today. It has no reporting term rows, and its grades live
  in Focus, which `base_powerschool__final_grades` does not read. Whether Miami
  belongs on this tab is an open scope question for the owner, not a bug to fix.

## Joins

| Parent                                                    | Join                                                                                          | Brings                            |
| --------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------- |
| `base_powerschool__final_grades`                          | `studentid`, `yearid`, `_dbt_source_project`, term name = `storecode`, `exclude_from_gpa = 0` | term and Y1 grades, `need_60`     |
| `base_powerschool__sections`                              | `sectionid`, `_dbt_source_project`                                                            | course name, credit type, teacher |
| `int_powerschool__gpa_term`                               | `studentid`, `yearid`, `_dbt_source_project`, term name                                       | `gpa_y1`, `gpa_term`              |
| suspension CTE over `int_deanslist__incidents__penalties` | `student_number`, academic year, `_dbt_source_project`                                        | suspension count and days         |

None of these joins carries `schoolid`. A student who changed high school
mid-year gets grades and term GPA from both schools attached to the current
enrollment; the uniqueness test fails only if two rows share a course number.

`int_powerschool__gpa_term` has duplicate rows on its natural key (#4938). They
do not reach this extract today: the grain test above passes. If it starts
failing, check #4938 first.

## The flags live in Tableau

The five flags, their thresholds, and why GPA and credits read projected values
are in the doc (_The five early warning flags_). Reproduce a flag from the
extract before opening the workbook. The over-age rule has never been reproduced
from the extract; say so rather than guessing a formula.

Anyone quoting an on-track percentage must say which `On Track Indicator`
setting produced it (All, Credits, or Core Fs); the doc's warning has the
spread.

## QA after a change

- Grain: `dbt build --select rpt_tableau__hs_early_warning_dashboard` runs the
  uniqueness test.
- Coverage: distinct students per school against
  `int_extracts__student_enrollments` with the same filters. A school with
  enrolled students and no extract rows is the terms-sheet failure above.
