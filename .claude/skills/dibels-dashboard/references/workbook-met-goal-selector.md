# Workbook runbook: the PM Met Goal selector and its grain

The Literacy Dashboard's `Region Overview - PM (Internal)` tab colours its bars
with `PM - Met Goal Selector`. This page is the runbook for fixing that selector
so a student lands in one segment per bar, and for any later change to it.
Zendesk ticket 484741 (2026-10-02) is the report that produced it.

## What's in here

- The symptom and its cause
- Reproduce it from the extract before editing anything
- The fix, step by step
- Verify the render
- Publish
- Close out

## The symptom and its cause

Symptom: with Met Goal Type on `Met Benchmark Goal` or `Met Standard Goal` and a
column selector on `Measure`, the segment labels in one bar add to more than
100% (22% + 89%, 73% + 93%).

Cause, read from the workbook XML on 2026-10-02:

- Sheet `Region Overview PM - Met Goal`. Colour is `PM - Met Goal Selector`
  (`[Calculation_370702545799553044]`), a CASE on `[Parameter 5]` (caption
  `PM - Met Goal Parameter`) returning one numeric flag per option:
  `met_pm_round_overall_criteria`, `met_measure_name_code_goal`,
  `met_measure_standard_goal`, `met_admin_benchmark_goal`. Aliases: null = No
  Data, 0 = Not Met, 1 = Met.
- The six column selectors are `Region Overview PM - Hierarchy Column #N`. Their
  `Measure` option maps to `expected_measure_name_code`; `Measure Standard` maps
  to `expected_measure_standard`.
- The label is `COUNTD(student_number)` with a `PctTotal` table calc
  (`CellInPane`).

`ORF` and `NWF` each carry two measure standards, and the standard-grain and
benchmark flags vary between them for the same student (see _Measure grain and
measure-standard grain differ by 15 points on ORF_ in `aimline-method.md`). A
`Measure` column holds both standards' rows, so a student who met Accuracy and
missed Fluency is a distinct student in the Met segment and in the Not Met
segment. The denominator counts them once. The sheet does filter
`model_type = Internal`, so this is not the Internal/Aimline double count.

The selector is also on `Region Overview PM - Student Roster` and
`Student Mastery by Term`, as a dimension in both. No sheet aggregates it as a
measure, so converting it to strings breaks no `AVG()`.

## Reproduce it from the extract before editing anything

Run this with the ticket's filters. Done when `segment_sum` exceeds `students`
on the bars the screenshot shows, and every segment count matches a label.

```sql
with
    base as (
        select
            school,
            grade_level_int,
            student_number,
            admin_benchmark_goal_status,
        from `teamster-332318`.kipptaf_tableau.rpt_tableau__dibels_dashboard
        where
            academic_year = 2026
            and model_type = 'Internal'
            and enroll_status = 0
            and expected_round_selection = 'Current'
            and region = 'Camden'
            and expected_measure_name_code = 'ORF'
            and grade_level_int between 5 and 8
            and coalesce(tutoring_nj, false) = false
    ),

    per_student as (
        select
            school,
            grade_level_int,
            student_number,
            countif(admin_benchmark_goal_status = 'Met Benchmark') > 0 as any_met,
            countif(admin_benchmark_goal_status = 'Did Not Meet Benchmark')
            > 0 as any_not_met,
            countif(admin_benchmark_goal_status = 'Not Tested') > 0 as any_not_tested,
            count(distinct admin_benchmark_goal_status) as n_status,
        from base
        group by school, grade_level_int, student_number
    )

select
    school,
    grade_level_int,
    count(*) as students,
    countif(any_met) as met,
    countif(any_not_met) as not_met,
    countif(any_not_tested) as not_tested,
    countif(any_met) + countif(any_not_met) + countif(any_not_tested) as segment_sum,
    countif(n_status > 1) as in_two_segments,
from per_student
group by school, grade_level_int
order by school, grade_level_int
```

Measured 2026-10-02: ten bars, all matching the screenshot. Hatch grade 8 had 73
students, 53 met, 68 not met, 49 in two segments.

## The fix, step by step

Desktop, not XML: the change is a calc, its colour legend, and aliases, and a
render cannot confirm a legend or a hover.

1. Take ownership. On Tableau Cloud, Production project, workbook
   `Literacy Dashboard` (luid `72b16a4a-b3a9-47e5-bdff-ae641d9ee9e6`): change
   the owner to yourself. Done when the workbook page shows your name as owner.
   A publish over another account's workbook is refused.
1. Download with the extract and record the revision number. That number is the
   restore point.
1. Add a boolean calc `PM - Columns At Standard Grain`: true when any of the six
   `Region Overview PM - Hierarchy Column #N Parameter` values equals
   `Measure Standard`.
1. Rewrite `PM - Met Goal Selector` so it returns the labelled twin at the grain
   the columns show, and carries no logic of its own beyond that choice:

   ```text
   CASE [PM - Met Goal Parameter]
   WHEN 'Met Overall Goal'   THEN [pm_round_status]
   WHEN 'Met Measure Goal'   THEN [measure_name_code_goal_status]
   WHEN 'Met Standard Goal'  THEN IF [PM - Columns At Standard Grain]
                                  THEN [measure_standard_goal_status]
                                  ELSE [measure_name_code_goal_status] END
   WHEN 'Met Benchmark Goal' THEN IF [PM - Columns At Standard Grain]
                                  THEN [admin_benchmark_goal_status]
                                  ELSE [measure_name_code_benchmark_status] END
   END
   ```

   The twins are listed in _The four goal grains each have a flag and a labelled
   twin_ in `aimline-method.md`. `measure_name_code_benchmark_status` is
   populated on Internal rows (checked 2026-10-02: Met Benchmark, Did Not Meet
   Benchmark, Not Tested).

1. Set the colour legend from the columns' real domains. Query them rather than
   typing from memory, since the four columns use different words:

   ```sql
   select
       'pm_round_status' as col, pm_round_status as value, count(*) as n,
   from `teamster-332318`.kipptaf_tableau.rpt_tableau__dibels_dashboard
   where model_type = 'Internal'
   group by col, value
   ```

   Repeat for `measure_name_code_goal_status`, `measure_standard_goal_status`,
   `admin_benchmark_goal_status` and `measure_name_code_benchmark_status`. Give
   every met value one colour, every not-met value one, and `Not Tested` the
   grey the sheet uses today. The old No Data alias sat on the null member; PM
   rows are no longer null, so drop it.

1. Open `Region Overview PM - Student Roster` and `Student Mastery by Term` and
   confirm the selector still renders as a label there. Done when both show
   words, not numbers.
1. Check `Region Overview PM - Met Growth` on the same dashboard. Its colour is
   a different calc (`[Calculation_1193735390436143108]`) over the same `COUNTD`
   percent-of-total. Set its columns to `Measure` and confirm its segments sum
   to 100%; if they do not, apply the same grain switch there.

## Verify the render

Render the dashboard once per cell of this grid, with the parameters set
explicitly through `viewFilters` (parameter captions as keys, see
`.claude/context/tableau.md`):

| Met Goal Type      | Column #3 = Measure | Column #3 = Measure Standard |
| ------------------ | ------------------- | ---------------------------- |
| Met Overall Goal   | sums to 100%        | sums to 100%                 |
| Met Measure Goal   | sums to 100%        | sums to 100%                 |
| Met Standard Goal  | sums to 100%        | sums to 100%                 |
| Met Benchmark Goal | sums to 100%        | sums to 100%                 |

Done when every bar in every cell sums to 100% within rounding, and the
`Met Benchmark Goal` / `Measure Standard` cell still shows Fluency and Accuracy
disagreeing (the two ORF bars differ). A grid where every cell agrees means the
grain switch is not firing.

Then re-run the reproduce query with `measure_name_code_benchmark_status` in
place of `admin_benchmark_goal_status` and confirm `in_two_segments` is 0 on
every bar.

## Publish

Publishing from Desktop as owner replaces production directly. Before you do:
the revision number from step 2 is written down, and the filter bar is reset
(Region on All, Admin Window on `Current`), because Desktop saves the filter
state at publish time (`diagnosing.md`, _In the extract but not on the
dashboard_). After publishing, render with no `viewFilters` and read the filter
bar.

A scripted publish instead goes through `tableau-workbook-xml`: review copy
first, two typed confirmations for production.

## Close out

- Reply on the ticket: the counts were right, the colour was paired with the
  wrong grain, and the fix is live.
- Record the date and what changed in `aimline-method.md` under _The workbook is
  the other half_ and in the published reference doc's PM Internal notes.
