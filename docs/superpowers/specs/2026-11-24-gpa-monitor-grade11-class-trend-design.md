# Cumulative GPA Monitor: end-of-11th-grade GPA by graduating class — Design

Issue: [#6478](https://github.com/TEAMSchools/teamster/issues/6478)

## Intent

KIPP Forward sets college matriculation goals for each graduating class. When a
class arrives at senior year with a weaker academic profile than the class
before it (for example, a smaller share at 3.5 and above), the goal has to
reflect that, and KIPP Forward has to be able to show why. They need to compare
graduating classes on the GPA they carried into the college application season:
cumulative unweighted GPA at the end of 11th grade, by high school.

The Trends pop-up on the Cumulative GPA Monitor already has a grade 11 chart
(`GPA - Splay over time`), but it is keyed to school year, hard-codes 2021 to
2025, and counts a student who repeated 11th grade in 2 years. This change
re-keys that chart to graduating class.

## Goals

- One chart: graduating classes as columns, one row per high school plus a total
  row on top, each cell a 100% stacked bar across the 5 GPA bands.
- The current 12th graders and the 6 classes before them, rolling forward each
  July with no workbook edit.
- Each student counted once, at their last completed 11th-grade year.
- The population stated on the chart: students enrolled at the end of 11th
  grade.

## Non-goals

- The Salesforce College Match GPA field. This view reads the warehouse's own
  cumulative GPA.
- `GPA - Trend by grade`, the other chart in the pop-up. It stays as it is.
- Student-years dropped when grades were stored at another school (#4343).
- Weighted GPA, Miami, and Paterson (neither has high school rows).

## Anti-goals

- A total row that disagrees with the school rows beneath it.
- An in-progress year's projection shown as an end-of-11th-grade result.
- Year logic in a Tableau calculated field that breaks at rollover.

## Approaches

1. **dbt flags, simple chart (chosen).** 2 boolean columns on the year extract
   carry the "last completed 11th-grade year" pick and the 7-class window. The
   worksheet filters on them. The rules are tested in dbt and roll forward with
   `current_academic_year`. Costs a PR, CI, and an extract refresh before the
   workbook publishes.
1. **Tableau only.** A FIXED LOD picks the latest 11th-grade year and a second
   calc derives the window from the newest class in the data. Ships without a
   PR, but nothing tests the calcs, the window drifts in summer, and a FIXED LOD
   ignores the region and honors filters unless they are added to context.
   Rejected for those reasons.
1. **A new one-row-per-class model.** Rejected: the request is to stay on the
   existing model, and it adds a data source to the workbook.

## Decided

- Measure: `cumulative_y1_gpa_unweighted`, the year-end value on the 11th-grade
  row.
- Bands: `gpa_band_label` with the dashboard's existing colors (`3.5+` through
  `below 2.0`).
- Columns: `graduation_year`, labelled "Class of YYYY", with the school year the
  class finished 11th grade beneath it; the newest class marked as the current
  12th graders.
- Rows: `school` (NCA, NLH, KHS today), with an "All high schools" total row on
  top that follows the Region parameter.
- Above each bar: the share at 3.0 or above. Inside each bar: the band
  percentages. Below each bar: the class size.
- Population note on the chart, and the honors filter kept. The school filter no
  longer applies to this chart, since every school has its own row.

### dbt

On `rpt_tableau__gpa_cumulative_year`, passed through
`rpt_tableau__gpa_goal_progress` (its select list and contract are kept by
hand):

- `is_last_completed_grade_11`: true on the row whose `academic_year` is the
  latest grade 11, non-`is_projected` year for that `student_number`, among the
  rows the extract already keeps (`rn_year = 1`, `is_enrolled_recent`, status
  and region filters).
- `is_grade_11_trend_class`: true when `graduation_year` is between
  `current_academic_year - 5` and `current_academic_year + 1`.

The population rule needs no new logic: `is_enrolled_recent` already keeps only
stints that ran through the last day of the school year.

## Left to the builder

- The exact SQL and tests, within `.claude/rules/dbt-sql.md` and the model's
  existing uniqueness test. At minimum, a test that `is_last_completed_grade_11`
  marks at most one row per `student_number`.
- Tableau mechanics for the total row (grand total moved to the top and
  relabelled), the 3.0+ label, and the class-size label, through the
  `tableau-workbook-xml` skill.
- Final caption wording, within the population and repeater rules above.
- Updating the `rpt_tableau__gpa_goal_progress` section of
  `docs/models/academic-health-data-model.md`.

### Calls made in this design (not discussed)

- Empty cells (NLH before 2023, KHS before 2024) render blank in Tableau rather
  than the mockup's "No class yet". The caption names when each school's data
  starts.
- A student who repeated 11th grade and left during the repeat year counts at
  their first 11th-grade year, the last one they finished enrolled.
- The chart keeps its current worksheet name and position in the Trends
  container, so dashboard actions that show and hide it keep working.

## Rollout

1. Merge the dbt change and let prod build both models.
1. Refresh the workbook extract so the new columns exist.
1. Publish a review copy of the workbook to a non-production project and check
   it against a direct query on `rpt_tableau__gpa_goal_progress`.
1. Publish to production after the owner confirms.
