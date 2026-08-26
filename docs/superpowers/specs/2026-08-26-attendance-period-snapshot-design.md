# Attendance period snapshot and chronic absence definition

Refs [#4994](https://github.com/TEAMSchools/teamster/issues/4994). Follow-up:
[#5015](https://github.com/TEAMSchools/teamster/issues/5015).

Supersedes `2026-08-26-chronic-absence-definition-alignment-design.md`, which
scoped only the definition fix and assumed the Cube measure families would stay.

## Summary

Two problems, one fix.

The chronic absence definition in `fct_student_attendance_daily` diverges from
every authority KTAF answers to. Separately, the Cube layer carries 30 duplicate
measures and 165 lines of `queryRewrite` to pick a period-end row out of a daily
fact.

Both dissolve if dbt publishes a **periodic snapshot** at period grain instead
of stamping period-end flags onto 12.8M daily rows.

## How we got here

We started by asking where Tesseract's new features could replace hand-written
`cube.js` logic. Most of them could not. Recording the dead ends with their
numbers, so they are not relitigated.

| Approach                                                   | Result                                                                                                                                 |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `rolling_window` with `trailing: unbounded`                | Emitted **zero** window functions and silently discarded the query's date range lower bound. Counted all enrollments in history.       |
| `rolling_window` with `type: to_date` plus `grain.include` | Generated SQL that BigQuery rejects: `rolling_source... is neither grouped nor aggregated`.                                            |
| Custom granularity via `origin`                            | **Silently ignored.** Two different origin values both bucketed on the calendar year. No error.                                        |
| Custom granularity via `offset: -6 months`                 | **Works.** Correct July-anchored academic year buckets.                                                                                |
| Multi-stage `rank` for period-end selection                | Correct SQL once `keep_only` was added, but **timed out past 150s**, and stayed slow scoped to a single month. Structural, not volume. |
| Multi-stage `grain.include` with no window                 | **Works and is fast**, roughly a two-level `GROUP BY`.                                                                                 |

Measured against the real view, with RLS and joins, cold and with no
pre-aggregation:

| Query                                     | Time              |
| ----------------------------------------- | ----------------- |
| Plain additive aggregate by academic year | 14.3s             |
| Multi-stage `grain.include`, no window    | 14.9s to 30.6s    |
| Legacy `_year_end`, 3 academic years      | 38.4s             |
| Legacy `_week_end`, one academic year     | 51.6s             |
| Multi-stage `rank`                        | timeout past 150s |

Two conclusions. Window functions at query time do not scale on this fact. And
the legacy anchor-flag path is itself slow — 51.6s sits inside the Cube MCP
server's 55 second poll deadline, which is the same failure
[#4333](https://github.com/TEAMSchools/teamster/issues/4333) fixed for the
assessment cubes. Nothing has hit it only because nothing consumes this view
yet.

Two mechanics to carry forward regardless of design:

- `keep_only` is mandatory on any multi-stage measure that orders by a
  dimension, or the ordering column lands in `PARTITION BY` and every row ranks
  first. It must name the base time dimension (`dates.date_day`), not a derived
  one, or a `granularity` query partitions too coarse and **silently** returns
  the wrong number.
- `attendance_date` must be `CAST({CUBE}.date_key AS TIMESTAMP)`. Unqualified,
  any multi-stage reference to it fails with
  `Column name date_key is ambiguous`.

## The definition

Every authority agrees on the comparison and on including mid-year leavers, and
differs only on the minimum-days threshold.

| Authority                        | Chronically absent when                         | Minimum days                 | Leavers  |
| -------------------------------- | ----------------------------------------------- | ---------------------------- | -------- |
| New Jersey, state accountability | absent 10% or more of days in membership        | 45 at a school               | included |
| New Jersey, federal EDFacts      | absent 10% or more                              | 10                           | included |
| Florida, covering Miami          | absent 10% or more of school days at the school | 10                           | included |
| KIPP Foundation                  | ADA at or below 90.0%                           | 10 at that individual school | included |

Decisions:

1. Chronically absent when ADA is **at or below 90.0%**.
1. Eligible at **10 or more membership days at the individual school**, counted
   cumulatively across the year, not per period.
1. Mid-year leavers are **included**.
1. The New Jersey 45-day threshold is out of scope
   ([#5015](https://github.com/TEAMSchools/teamster/issues/5015)).

Three defects this corrects, sized on AY2025:

| Defect                                                   | Enrollments affected                                                                                          |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `_running_ada < 0.90` excludes students at exactly 90.0% | 198 sit there; 119 are missed, and the other 79 are caught only because their float average lands under `0.9` |
| No minimum-days threshold                                | 147 under 10 days, 116 of them counted chronically absent                                                     |
| Year-end anchor drops mid-year leavers                   | 180, of which 72 are chronically absent                                                                       |

`rpt_tableau__okrts_referrals` already uses `unweighted_ada <= 0.90`. The repo
currently ships two definitions that disagree; this makes them agree.

## The model

A new dbt model, one row per enrollment per period.

| Column                   | Meaning                                                             |
| ------------------------ | ------------------------------------------------------------------- |
| `student_enrollment_key` | The stint                                                           |
| `schoolid`               | The school the threshold applies at                                 |
| `period_type`            | `year`, `month`, or `week`                                          |
| `period_start_date`      | Bucket start; `week` uses the PowerSchool school week               |
| `period_end_date`        | The enrollment's **own** last membership day in the bucket          |
| `n_membership_days_ytd`  | Cumulative membership days at this school through `period_end_date` |
| `ytd_ada`                | Cumulative ADA through `period_end_date`                            |
| `is_ca_eligible`         | `n_membership_days_ytd >= 10`                                       |
| `is_chronically_absent`  | `ytd_ada <= 0.90`, computed on accumulated counts, not the float    |

Rough size: about 11,300 enrollments times roughly 51 periods, so **under 600K
rows against 12.8M**.

Compute `is_chronically_absent` from the accumulated counts rather than by
comparing the averaged float:

```sql
-- 198 AY2025 enrollments sit at exactly 90.0%. Comparing the float average
-- sorts 79 of them one way and 119 the other, on representation alone.
cumulative_present * 10 <= cumulative_membership * 9 as is_chronically_absent
```

## Daily fact or period snapshot

Both stay. They answer different questions.

Use **`fct_student_attendance_daily`** when the question is about a _day_:

- Was this student absent on 14 October?
- The daily calendar heatmap, which the KIPP Foundation criteria require.
- Attendance by day of week.
- Any per-day drill-down or student-level daily list.

Use the **period snapshot** when the question is about a _rate as of a point in
time_:

- Chronic absence rate, at any grain.
- ADA tier distribution.
- Year-over-year and month-over-month trends.
- Anything that today needs an anchor flag.

The rule: "on this day" reads the daily fact, "as of this period" reads the
snapshot. The snapshot is built from the daily fact, so they cannot disagree.

## Enrollments that do not span the period

A student enrolled 1 September and withdrawn 10 October is the case that breaks
naive designs, and it is worth stating exactly.

- They get a **September row** and an **October row**. The October row's
  `period_end_date` is 10 October, their own last membership day, not the
  school's month end. `ytd_ada` is their cumulative rate through that date.
- They get **no November row and none after**. A period with no membership day
  produces no row. Nothing is carried forward, so a withdrawn student never
  becomes a stale ghost in later periods.
- They **are** in the year row, with ADA over their ~28 enrolled days, subject
  to the 10-day minimum. This is the leaver fix: it is what all four authorities
  require, and what the current year-end anchor gets wrong.
- Eligibility is evaluated on **cumulative** membership days, not the period's
  own. A student with 6 days in October but 40 days year-to-date is eligible in
  October. Applying the threshold per period would exclude anyone in a short
  month.

This matches what the existing per-stint `is_month_end_record` anchor already
does, so month and week numbers should not move. Only the year figure changes,
by the 180 leavers.

One property to document for consumers: because a withdrawn student stops
producing rows, a month-over-month CA trend has a shifting denominator. That is
correct — they are not enrolled — but the composition changes between points, so
the series is not a fixed cohort.

## Cube changes

- `student_attendance` keeps only day-level measures and dimensions.
- A new cube reads the period snapshot. `period_type` is an ordinary dimension,
  so one measure family serves all three grains.
- The 30 `_year_end`, `_month_end`, and `_week_end` measures are removed.
- The `queryRewrite` snapshot block is removed: `SNAPSHOT_CUBES`,
  `SNAPSHOT_MEASURE_STEMS`, `SNAPSHOT_ANCHOR_DIMENSIONS`,
  `SNAPSHOT_ANCHOR_OVERRIDES`, and the granularity validation. `cube.js` keeps
  only authentication, access, and emulation.

No Tesseract feature is required. The `offset: -6 months` academic-year
granularity remains useful for day-level year bucketing and is worth adding
independently.

## Impact

AY2025 chronic absence moves from **24.8% to 26.2%**. The current defects partly
cancel, so the headline moves less than the composition does.

Nothing consumes `fct_student_attendance_daily` today except three dbt tests and
the `cube.yml` exposure, so no published figure moves on merge. That will not be
true later; land this before the dashboards do.

## Testing

Boundary unit tests, since every defect here is a boundary defect:

- ADA of exactly 90.0% is chronically absent; 90.01% is not.
- Exactly 10 cumulative membership days is eligible; 9 is not.
- Membership days count per school: 6 days at one school plus 6 at another is
  eligible at neither.
- A student withdrawn 10 October has an October row dated 10 October, no
  November row, and appears in the year row.
- A student with 6 days in October but 40 year-to-date is eligible in October.

Reconciliation against the figures on
[#4994](https://github.com/TEAMSchools/teamster/issues/4994): 11,153 counted
today, 180 leavers restored, 119 added at exactly 90.0%, 147 excluded under 10
days. Month and week counts must not move.

## Out of scope

- The New Jersey 45-day figure
  ([#5015](https://github.com/TEAMSchools/teamster/issues/5015)).
- Pre-aggregations. At under 600K rows they may not be needed; measure first.
  The 55 second MCP deadline issue is real but separate.
- `student_enrollment_key` splitting a student who exits and re-enrolls at the
  same school into two calculations. Every authority accumulates days at the
  school across the year.
- `ada_tier` label wording. The boundaries match KIPP Foundation; the
  descriptions in the properties file do not.

## Open question for KIPP Foundation

Their criteria contradict themselves. Item 1 calls Tier 1 and Tier 2 on track at
90% or above ADA. Item 8 says chronic absence is ADA at or below 90.0%. A
student at exactly 90.0% is both.
