# Projected BA enrollment goals alongside cumulative GPA goals

Refs [#5140](https://github.com/TEAMSchools/teamster/issues/5140).

## Problem

Leaders track cumulative GPA against two goals, not one.

The first is the share of high school students at a cumulative unweighted GPA of
3.0 or higher. That goal is in `int_google_sheets__gpa_goals` today: 69% at
grade 9, 64% at grade 10, 60% at grade 11, 56% at grade 12 for AY2026.

The second is a projected four-year college enrollment goal. It is met when that
same share **plus 15 percentage points** reaches the target. A school at 35% of
students at 3.0+ meets a 50% enrollment goal, because 35 + 15 = 50.

Only the first exists in the warehouse. The second lives in leaders' heads and
in whatever calculation a dashboard author writes.

### The two goals are on different scales

This is the whole difficulty, and it is easy to miss.

The GPA goal is a **share of students**. The enrollment goal is a **projected
enrollment rate**. Both would sit in the `goal` column as a number between 0 and
100, look identical, and mean different things.

The 15 applies to the **actual only**, never to both sides.
`actual + 15 >= goal`. It is a unit conversion between the two scales, not a
presentation offset. An offset applied to both sides would leave the gap
unchanged and be purely cosmetic; this one narrows the gap by 15 points, which
is the point of it.

### Adding rows without the offset publishes wrong answers

`int_google_sheets__gpa_goals` feeds `int_gpa__goal_aggregations`, which feeds
`rpt_tableau__gpa_goals`. That model computes `metric_rate` and compares it to
`goal`. Two published surfaces read it: the `gpa_goals_dashboard` exposure, and
the GPA Goals tile on Academic Health Home.

Add enrollment goal rows with no record of the 15, and that pipeline compares a
35% GPA rate against a 50% enrollment goal and publishes **failing** for a
school that has met its goal. Nothing errors, no test fails, and the only
consumer that knows better is one Tableau calculation on a dashboard that has
not shipped yet.

That is the same class of defect as the two-data-source problem that
[#5097](https://github.com/TEAMSchools/teamster/issues/5097) removed: a number
that reads as comparable and is not.

## What this builds

Record the adjustment beside the goal, so the comparison is correct for every
consumer rather than only the one that was told about it.

### The offset column

Add one column to the goals sheet holding the amount added to the actual before
comparison. It is `15` on enrollment rows and `0` on the existing GPA rows.

The offset is flat — it does not vary by grade, region or school. A single
constant would therefore work today. It is stored as a column anyway for three
reasons: a consumer reading the goals sheet can compute the comparison correctly
without external knowledge; a change from 15 to some other number is a sheet
edit rather than a code change; and a constant that lives in a workbook while
the goal lives in a sheet is a pair that drifts.

Ops edits this sheet directly, so the column is a sheet change before it is a
dbt change.

### The enrollment goal rows

One row per grade band and organisational level, the same shape the GPA goals
already use. The goal differs by grade; the offset does not.

They carry their own `metric` value rather than sharing
`cumulative_gpa_unweighted`.

**Why a distinct metric is required, not stylistic.**
`int_gpa__student_goal_definitions` is grained
`(academic_year, student_number, metric)` and carries a
`dbt_utils.unique_combination_of_columns` test at `severity: error`. A second
goal row sharing `cumulative_gpa_unweighted` over the same grade band matches
the same student twice through the
`grade_level between grade_low and grade_high` join and fails that test. It is
the identical failure mode the overlapping-band guard exists to catch. A
distinct metric keeps the grain intact and the new rows flow through the
intermediate unchanged.

**Name it for the measurement, not the framing.** The threshold is still 3.0 on
cumulative unweighted GPA. A metric named for enrollment, carrying a GPA
threshold, sends the next reader looking for an enrollment field that does not
exist. `cumulative_gpa_unweighted_ba_proxy` says both what is measured and what
it is used for.

### Keeping the published pipeline unchanged

`int_gpa__goal_aggregations` must exclude the new metric, so nothing reaches
`rpt_tableau__gpa_goals` and the two published surfaces keep reporting exactly
what they report today.

This is a defensive filter whose entire effect is "published output stays
byte-identical when a new metric appears." Verification is a row-level
comparison of `rpt_tableau__gpa_goals` before and after, which must show no
difference.

Folding the enrollment goal into that model later is a separate decision. It
would require teaching every consumer about the offset, which is exactly the
work this design defers rather than does badly.

### Carrying the goal to the dashboard

`rpt_tableau__gpa_goal_progress` filters to
`metric = 'cumulative_gpa_unweighted'` and is grained
`(student_number, academic_year)` with its own `severity: error` uniqueness
test.

The enrollment goal arrives as **additional columns** through a second left join
filtered to the new metric — never as additional rows, which would fan the
wrapper out and fail that test.

That is the goal proportion at each of the three rungs, plus the offset: four
columns. The threshold does not need repeating — it is 3.0 on cumulative
unweighted GPA for both goals, and `gpa_goal_threshold` already carries it.

The wrapper's select list is written out by hand because the repo forbids
`select *` in a final `rpt_` select. These columns must be added to both the
select list and the contract yml or the build fails.

### In Tableau

The comparison reads the offset rather than hardcoding it:

```text
[% at 3.0+] + [BA offset] >= [BA goal]
```

## Downstream impact

Nothing published changes. `rpt_tableau__gpa_goals`,
`rpt_tableau__gpa_cumulative_year` and `rpt_tableau__student_course_grades` are
untouched, and the exclusion filter above is what keeps the first of those true
once new rows exist in the sheet.

`rpt_tableau__gpa_goal_progress` gains columns. It is contract-enforced and read
only by the Cumulative GPA Monitor, which is not yet published.

## Verification

- `rpt_tableau__gpa_goals` output is unchanged, compared row for row against its
  pre-change state. This is the check that proves the published surfaces are
  safe.
- `int_gpa__student_goal_definitions` still passes its uniqueness test at
  `(academic_year, student_number, metric)` with the new metric present.
- `rpt_tableau__gpa_goal_progress` still passes its uniqueness test at
  `(student_number, academic_year)` — proving the second join added columns and
  not rows.
- Row counts on the wrapper are unchanged from before the second join.
- For AY2026, the enrollment goal columns are populated for grades 9 through 12
  and null below grade 9, matching how the existing goal columns behave.
- The offset reads 15 on enrollment rows and 0 on GPA rows, with no nulls.

## Open questions

These need answers before implementation, not during.

1. **The metric's exact name.** `cumulative_gpa_unweighted_ba_proxy` is the
   proposal. Ops types this into a sheet, so it should be something they will
   enter consistently.
2. **The enrollment goal for each grade band and organisational level.** The 50%
   in the example is illustrative. The real numbers are needed for all four
   grades, at network, region and school level, for the academic years in scope.
3. **Who adds the sheet column.** The offset column is a Google Sheet edit
   before it is a dbt change. If Ops adds it, the sheet and the staging contract
   must land together or the build breaks on a missing column.
4. **What the display does above 100%.** The offset can push a rate past 100%.
   Nothing breaches it today — the highest school-grade rate is 74.3% at NCA
   grade 9, giving 89.3% — but that is about ten points of headroom. Capping
   silently hides the proxy breaking down; letting it break visibly is ugly but
   honest. This is a judgement call for the design owner.

## Out of scope

- Folding the enrollment goal into `rpt_tableau__gpa_goals` and the published
  dashboards. Deferred deliberately; see above.
- Rewriting the Cumulative GPA Monitor runbook onto the single data source.
  Related and worth doing in the same pass, but it is a separate change to a
  separate artifact.
- The `not_null` gaps on `stg_google_sheets__gpa_goals`. Its `goal` column
  carries `expression_is_true: between 0 and 100` with no paired `not_null`, and
  `org_level`, `metric` and `direction` carry `accepted_values` with no paired
  `not_null` — and `accepted_values` does not reject NULL. Pre-existing, worth
  fixing, and worth fixing separately so this change's diff stays readable.

## Reference

Measured 2026-09-03, AY2026, network rung, `cumulative_gpa_unweighted`:

| Grade | GPA goal | Actual | Actual + 15 |
| ----- | -------- | ------ | ----------- |
| 9     | 69%      | 68.6%  | 83.6%       |
| 10    | 64%      | 57.4%  | 72.4%       |
| 11    | 60%      | 48.2%  | 63.2%       |
| 12    | 56%      | 45.9%  | 60.9%       |

Goals exist only for AY2025 and AY2026, while `rpt_tableau__gpa_cumulative_year`
spans 2004 through 2026. Every high school row before AY2025 has no goal at all,
and the enrollment goal will behave the same way.
