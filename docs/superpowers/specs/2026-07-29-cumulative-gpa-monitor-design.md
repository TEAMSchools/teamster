# Cumulative GPA Monitor — Design

Issue: [#4619](https://github.com/TEAMSchools/teamster/issues/4619)

## Problem and motivation

KIPP Forward needs a single view of high-school cumulative GPA against goals:
where each cohort sits relative to its target, how the GPA distribution is
splayed, how that distribution has moved over years, how it differs across
student groups, and which students sit just below the 3.0 line.

A local React mockup established the intended shape. This design maps every mark
in that mockup to a real warehouse column, keeps what the data supports, and
cuts what it does not.

The same metric is already computed in two places, and this dashboard would make
a third. Keeping them reconciled is the core risk this design manages:

1. The topline cascade publishes an indicator named
   `Projected Unweighted Cumulative GPA`, computed weekly in
   `int_topline__student_metrics` as
   `countif(cumulative_y1_gpa_projected_unweighted >= 3.00)`, with its own goal
   system.
1. The GPA goal scaffold (#4581 / #4598) computes the same measure at year grain
   from the same column, with its own goal sheet.
1. This dashboard would compute it a third time.

All three must agree. The rule that makes them agree is in _Goal integration_
below.

## Non-goals and out of scope

- **College enrollment projection and enrollment goals.** The mockup's headline
  tile — projected college enrollment versus goal, the gap-to-goal box, the
  students-to-move count, and the enrollment-goal diamonds on the by-grade chart
  — rests on an assumed constant: enrollment approximately equals the
  3.0-and-above rate plus 15 points. Nothing in the warehouse produces that
  relationship. Fitting it means joining historical graduating cohorts' HS
  cumulative GPA to their actual `kippadb` college enrollment. That is a
  distinct analytical build and gets its own spec.
- **The topline cascade's goals.** Unchanged. GPA remains a topline metric there
  independently.
- **The gradebook dashboard's Y1 landing surfaces.** Separate work, tracked
  elsewhere.
- **Marts or Cube surfacing** of these measures.

## What the source data supports

The workbook's Tableau data source relates two BigQuery tables:

| Table                                | Grain                                      | Window               |
| ------------------------------------ | ------------------------------------------ | -------------------- |
| `rpt_tableau__student_course_grades` | student x term x course section x category | current + prior year |
| `rpt_tableau__gpa_cumulative_year`   | student x academic year                    | 2004 to 2026         |

Two facts about that pairing drive the whole design.

### The relationship is defective

The relationship expression is `[student_number] = [student_number]` with no
academic year. Any view touching both sides without pinning a single year fans a
student across every year they attended. Current seniors carry between one and
ten rows in the year table, reaching back to 2017, because it covers their
middle-school years too.

This dashboard therefore reads **one table**. Not a repaired relationship — a
single table, so the fan-out is structurally impossible rather than merely
filtered away.

### The two-year window does not truncate cumulative GPA

Cumulative GPA is not assembled from extract rows. It is computed upstream in
`int_powerschool__gpa_cumulative` from the full PowerSchool transcript, then
stamped on as a single value. Verified against prod for academic year 2026:

| Grade | Avg earned cumulative credits | Avg cumulative unweighted GPA |
| ----- | ----------------------------: | ----------------------------: |
| 9     |                           0.3 |                          0.12 |
| 10    |                          36.6 |                         2.700 |
| 11    |                          70.3 |                         2.713 |
| 12    |                         106.1 |                         2.714 |

A senior's GPA reflects roughly 106 credits — three full years — while the
course-grain extract holds two years of course rows. What the window costs is
**drill-down**: which courses produced a given GPA is answerable for two years,
not four. This dashboard drills to the current year's needed-GPA, so the window
is not a constraint.

## Architecture

One model changes. No new models on the GPA side.

```text
int_powerschool__gpa_cumulative_year   (student x year, 2004 to 2026)
int_extracts__student_enrollments      (that year's enrollment attributes)
int_powerschool__gpa_cumulative        (current state: actual, projected, needed, bands)
int_powerschool__gpa_term              (posted Y1 grades, for the default-year flag)
                    |
                    v
      rpt_tableau__gpa_cumulative_year          <- EXTENDED
                    +
      rpt_tableau__gpa_goals                    <- from #4598, unchanged
                    |
                    v
        Tableau: Cumulative GPA Monitor
```

### The enrichment join

`int_powerschool__gpa_cumulative` is keyed on `studentid` and `schoolid` per
source project, with **no academic year** — it is current-state only. It already
carries everything the dashboard needs beyond what the year model has: actual
and projected unweighted cumulative GPA, both band columns,
`gpa_needed_for_cumulative_3_0`, `is_cumulative_3_0_attainable`, and credit
counts.

Because it is current-state, it must attach to the current-year row only. The
year model already flags that row:

```sql
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gcc
    on gcy.studentid = gcc.studentid
    and gcy.schoolid = gcc.schoolid
    and gcy._dbt_source_project = gcc._dbt_source_project
    /* current-state enrichment attaches only to the current-year row; without
       this gate, today's values get stamped onto 22 years of history */
    and gcy.is_projected
```

`is_projected` is true for exactly the current academic year's rows and no
others — confirmed against prod across all 23 years present.

### New columns

| Column                                        | Source                             |
| --------------------------------------------- | ---------------------------------- |
| `cumulative_y1_gpa_unweighted_as_of_today`    | `gcc.cumulative_y1_gpa_unweighted` |
| `cumulative_y1_gpa_projected_unweighted`      | `gcc`                              |
| `cumulative_y1_gpa_unweighted_band`           | `gcc`                              |
| `cumulative_y1_gpa_projected_unweighted_band` | `gcc`                              |
| `gpa_band_as_of_today_label`                  | derived, see below                 |
| `gpa_band_projected_label`                    | derived, see below                 |
| `gpa_needed_for_cumulative_3_0`               | `gcc`                              |
| `is_cumulative_3_0_attainable`                | `gcc`                              |
| `is_on_cusp_3_0`                              | derived                            |
| `potential_gpa_credits_current_year`          | `gcc`                              |
| `is_latest_graded_year`                       | derived, see below                 |

The existing `cumulative_y1_gpa` and `cumulative_y1_gpa_unweighted` columns keep
their current meaning — the year-end value, where the current-year row already
holds the projection — so nothing downstream shifts.

The `_as_of_today` suffix on the new column is deliberate and load-bearing. It
sits beside the existing `cumulative_y1_gpa_unweighted`, which carries a
different meaning on the same row: the existing column is the year-end value,
the new one is the running value as of the last gradebook sync. Naming the new
column `_actual` would invite exactly the mix-up this dashboard is trying to
avoid.

`is_on_cusp_3_0` is
`cumulative_y1_gpa_projected_unweighted between 2.75 and 2.999`.

### Five-band labels

The upstream bands are **four**: `1` is below 2.00, `2` is 2.00 to 2.49, `3` is
2.50 to 2.99, `4` is 3.00 and above. The dashboard needs **five** — it splits
3.5 and above out, and the at-3.5-and-above tile depends on that split.

Band `4` is not redefined to make room. It has existing arithmetic consumers:
`int_extracts__student_enrollments` compares
`cumulative_y1_gpa_projected_unweighted_band < cumulative_y1_gpa_unweighted_band`.
Adding a fifth value would silently change the meaning of that comparison.
Instead a labeled string is derived in the extract from the raw GPA value, and
the integer bands pass through untouched:

```sql
case
    when gcc.cumulative_y1_gpa_projected_unweighted >= 3.50
    then '3.5+'
    when gcc.cumulative_y1_gpa_projected_unweighted >= 3.00
    then '3.0-3.49'
    when gcc.cumulative_y1_gpa_projected_unweighted >= 2.50
    then '2.5-2.99'
    when gcc.cumulative_y1_gpa_projected_unweighted >= 2.00
    then '2.0-2.49'
    when gcc.cumulative_y1_gpa_projected_unweighted < 2.00
    then 'below 2.0'
end as gpa_band_projected_label,
```

`gpa_band_as_of_today_label` mirrors this exactly, reading
`gcc.cumulative_y1_gpa_unweighted` instead.

### The default-year flag

Academic year 2026 is SY26-27. As of late July 2026 it has **zero posted Y1
grades** while carrying loaded schedules — verified two ways: only 55 of 684
ninth graders have any cumulative GPA, and `int_powerschool__gpa_term` has 0
rows with a non-null `gpa_y1` for that year against 22,484 for 2025. A
default-to-max-year would open the dashboard on an empty view for roughly two
months every year.

Cumulative earned credits cannot serve as the signal, because they include prior
years: 2026 seniors already show 106 earned credits in a year that has not
started. Posted Y1 grades is the signal that works. Note the conversion —
`int_powerschool__gpa_term` carries `yearid`, not `academic_year`, and the
canonical mapping is `yearid + 1990`:

```sql
graded_years as (
    select distinct yearid + 1990 as academic_year,
    from {{ ref("int_powerschool__gpa_term") }}
    where gpa_y1 is not null
)
```

`is_latest_graded_year` is true where the row's `academic_year` equals the
maximum from that set. The logic lives in dbt, not in a Tableau calculated field
that would silently break each August.

### Also in scope for the same change

- **Add the missing exposure.** `rpt_tableau__gpa_cumulative_year` has no
  exposure and no downstream refs — the only Tableau extract in this family
  without one, against a repo convention that every external consumer has one.
- **Update the model docstring.** It currently states the table is related to
  `rpt_tableau__student_course_grades` on `student_number`; that guidance is
  what produced the fan-out and should be corrected.

## Goal integration

Goals come from `rpt_tableau__gpa_goals` (#4598). Three sheet rows cover the
mockup's two goal frameworks:

| `org_level` | `region` | `grade_low`-`grade_high` | `metric`                    | `threshold` | `direction` | `goal` |
| ----------- | -------- | ------------------------ | --------------------------- | ----------- | ----------- | ------ |
| `region`    | Newark   | 9-9                      | `cumulative_gpa_unweighted` | 3.0         | `>=`        | 39     |
| `region`    | Camden   | 9-9                      | `cumulative_gpa_unweighted` | 3.0         | `>=`        | 39     |
| `org`       |          | 11-11                    | `cumulative_gpa_unweighted` | 3.0         | `>=`        | 41     |

Goal attainment is measured on `cumulative_y1_gpa_projected_unweighted` — the
same column the topline cascade and the goal scaffold both read. This is the
rule that keeps the three computations reconciled.

Current actual is a **separate monitoring series and is never compared to a
goal**. Mixing the two bases is what would produce a headline that disagrees
with the topline dashboard for the same cohort on the same day.

## Dashboard composition

Single-table data source. No relationship.

| Surface                            | Field or logic                                                  |
| ---------------------------------- | --------------------------------------------------------------- |
| At 3.0 and above                   | `countd` of projected at or above 3.0 over `countd` of all      |
| Average cumulative GPA             | `avg(cumulative_y1_gpa_projected_unweighted)`                   |
| At 3.5 and above                   | projected band label of `3.5+`                                  |
| Students to move                   | not at 3.0 and `is_cumulative_3_0_attainable`                   |
| On the cusp                        | `is_on_cusp_3_0`                                                |
| Goal frameworks, both              | `rpt_tableau__gpa_goals`, three rows                            |
| Foundation goal by region          | goal region rows against the rate                               |
| Goal versus actual by grade        | bar is the rate; reference line is the goal                     |
| Distribution, actual vs projected  | both band labels                                                |
| Movement above 3.0                 | derived from the band labels                                    |
| Splay across grades and over years | band label by grade, and by academic year                       |
| Trend by grade                     | year table history                                              |
| Equity cuts and MLL by region      | demographics already on the year table                          |
| Cusp roster                        | `gpa_needed_for_cumulative_3_0`, `is_cumulative_3_0_attainable` |

The roster shows **credits in progress**, from
`potential_gpa_credits_current_year`, rather than the mockup's course count. No
course-count column exists, and for a GPA conversation credits are the more
directly relevant quantity.

## Region coverage

Newark and Camden only. This is structural, not a pipeline gap. Across every
year in `int_extracts__student_enrollments`:

| Region   | HS students, ever | Latest year          |
| -------- | ----------------: | -------------------- |
| Newark   |             5,549 | 2026                 |
| Camden   |             1,410 | 2026                 |
| Paterson |                 0 | 2026, ES and MS only |
| Miami    |                 0 | 2025                 |

Paterson runs elementary and middle only. The existing
`region in ('Newark', 'Camden')` filter in the extract is correct for a
high-school dashboard, and the trailing `TODO(#4340): add Paterson` comment
should be replaced with a note recording why. The region dimension stays in
place so a future Paterson high school appears automatically.

This also removes the Paterson union work from this build's critical path. That
gap is real for MS and ES metrics and remains tracked under #4581, but it does
not gate this dashboard.

## Privacy and access

The cusp roster shows student names alongside GPA, and equity cuts render at
full granularity including small cells. Access control is the **existing Tableau
region and role gates**, not an in-workbook row-level-security calculation and
not a small-n suppression rule.

The implementation plan should name which Tableau groups the workbook is
published to, so a reviewer can verify the gate rather than assume it.

## Known behavioral caveats

Actual and projected cumulative GPA are **identical on a completed year** and
near-equal before a year begins. They diverge only while courses are in progress
with grades posted, roughly October through May. Verified against prod:

| Year              | Grade | Avg actual | Avg projected |
| ----------------- | ----- | ---------: | ------------: |
| 2025, complete    | 9     |      2.550 |         2.550 |
| 2025, complete    | 12    |      2.764 |         2.764 |
| 2026, not started | 9     |      0.114 |         0.114 |
| 2026, not started | 12    |      2.714 |         2.714 |

On a finished year the projection has resolved to the actual. On a year that has
not started there are no in-progress grades to project from, so both carry the
prior cumulative.

The mockup shows a permanent two-bar comparison. In production those bars are
identical for about four months and near-empty for two more. The distribution
panel needs an honest treatment: either collapse to a single bar when the two
measures are equal, or label the panel as in-session-only.

## Testing

- Keep the existing `unique_combination_of_columns` on `student_number` and
  `academic_year`.
- `not_null` on both band labels for HS rows with a non-null cumulative GPA.
- `expression_is_true` that `is_latest_graded_year` is true for exactly one
  `academic_year`.
- `accepted_values` on both band labels.
- Reconcile the at-3.0-and-above rate against the topline cascade's
  `Projected Unweighted Cumulative GPA` indicator for the same year and grain.
  They read the same column, so a mismatch means the filter sets differ.

## Dependencies

- **#4598 must merge** to supply `rpt_tableau__gpa_goals`. Its dbt Cloud run is
  currently failing on head `6485d90` and needs diagnosis first. This is the
  only blocker.
- Ops populates the three goal-sheet rows in _Goal integration_.

## Rollout and sequencing

1. Diagnose and fix the failing dbt Cloud run on #4598; merge it.
1. Ops adds the three goal rows to the GPA goals sheet.
1. Extend `rpt_tableau__gpa_cumulative_year`, add the exposure, correct the
   docstring, add tests.
1. Build the Tableau workbook against the single extended table.
1. Reconcile against the topline indicator before publishing.
1. Separate spec: fit the GPA-to-college-enrollment relationship from historical
   `kippadb` cohorts and add the enrollment surfaces to tab one.
