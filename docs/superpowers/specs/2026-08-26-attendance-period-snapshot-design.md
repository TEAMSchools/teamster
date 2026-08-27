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
1. **Tier 2 starts strictly above 90.0%**, so Tier 3 covers 80% through 90.0%
   inclusive. See below.
1. The New Jersey 45-day threshold is out of scope
   ([#5015](https://github.com/TEAMSchools/teamster/issues/5015)).

Three defects this corrects, sized on AY2025:

| Defect                                                   | Enrollments affected                                                                                                                                                                                                                                                                                    |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_running_ada < 0.90` excludes students at exactly 90.0% | 198, and **all 198** are missed. IEEE division is correctly rounded, so `avg()` over an exact 9/10 ratio always yields the same double as the literal `0.90`, and `0.9 < 0.9` is false every time. An earlier draft claimed 79 were caught by float scatter; there is no scatter, and they do not exist |
| No minimum-days threshold                                | 147 student-school pairs under 10 cumulative days, of which 100 were counted chronically absent. An earlier draft paired 147 with 116, mixing pair grain and stint grain in one figure                                                                                                                  |
| Year-end anchor drops mid-year leavers                   | 136 pairs restored, 61 of them chronically absent at pair grain. An earlier draft said 180 and 72, both stint-grain                                                                                                                                                                                     |

`rpt_tableau__okrts_referrals` already uses `unweighted_ada <= 0.90`. The repo
currently ships two definitions that disagree; this makes them agree.

### The tier boundary has to move with the threshold

`ada_tier` currently assigns Tier 2 at `_running_ada >= 0.90`, so exactly 90.0%
lands in Tier 2. Once chronic absence is `at or below 90.0%`, the same **198
AY2025 enrollments** are Tier 2 — which `pct_tier_1_2` reports as on track — and
chronically absent at the same time.

KIPP Foundation's criteria carry this contradiction themselves, so there is no
authority to defer to. Moving Tier 2's lower bound to strictly above 90.0% makes
Tier 1 plus Tier 2 mean exactly "not chronically absent", which is what a reader
of the dashboard will assume. The cost is a hair's deviation from KIPP
Foundation's stated Tier 2 range of 90 to 94%, which goes in the note to them.

Derive both from one expression, so they cannot drift apart again. With Tier 2
starting strictly above 90.0%, chronic absence is exactly Tier 3 plus Tier 4:

```sql
case
    when ytd_membership = 0 then null
    when ytd_present * 100 >= ytd_membership * 95 then 'Tier 1'
    when ytd_present * 10 > ytd_membership * 9 then 'Tier 2'
    when ytd_present * 10 >= ytd_membership * 8 then 'Tier 3'
    else 'Tier 4'
end as ada_tier,

ada_tier in ('Tier 3', 'Tier 4') as is_chronically_absent
```

Integer comparison rather than a threshold on the averaged float, so the 198
enrollments at exactly 90.0% land in Tier 3 deterministically. The
`ytd_membership = 0` guard is load-bearing: without it `0 >= 0` makes an
enrollment with no membership days Tier 3.

Cube computes nothing. Its measures stay `count_distinct` filtered on
`ada_tier`, as they are today.

## The model

A new dbt model, one row per enrollment per period.

| Column                  | Meaning                                                                 |
| ----------------------- | ----------------------------------------------------------------------- |
| `student_key`           | The student                                                             |
| `location_key`          | The school the threshold applies at                                     |
| `period_type`           | `year`, `month`, or `week`                                              |
| `period_start_date_key` | Bucket start; `week` uses the PowerSchool school week                   |
| `period_end_date_key`   | The enrollment's **own** last membership day in the bucket              |
| `n_membership_days_ytd` | Cumulative membership days at this school through `period_end_date_key` |
| `ytd_ada`               | Cumulative ADA through `period_end_date_key`                            |
| `is_ca_eligible`        | `n_membership_days_ytd >= 10`                                           |
| `is_chronically_absent` | `ytd_ada <= 0.90`, computed on accumulated counts, not the float        |
| `ada_tier`              | Tier 1 to 4; `is_chronically_absent` derives from it                    |
| `is_truant`             | Truancy status as of `period_end_date_key`                              |

Measured size, not estimated: **3.6M rows against the daily fact's 12.8M**, a
3.5x reduction. One academic year is about 546K rows — roughly 11,200
student-school pairs times the 51 periods in a year. The model carries the full
history the daily fact carries, with no academic-year floor, matching its sister
mart `fct_student_attendance_daily`.

An earlier draft of this spec put the total at under 750K. That was one year's
worth mistaken for the whole model. The reduction is real but smaller than first
claimed, so the pre-aggregation question stays genuinely open rather than being
settled by row count alone.

### Build from the intermediate model, not the fact plus a dim join

Source the snapshot from `int_students__attendance_daily`, which carries
`schoolid` directly. Measured on AY2025: zero null `schoolid`, and 11,333
distinct stints against the fact's 11,333 distinct `student_enrollment_key`
values. Complete coverage, nothing dropped.

Do **not** resolve school by joining the fact to `dim_student_enrollments`. That
join is lossy: 960 of the 11,333 AY2025 attendance enrollment keys, or 8.5%,
have no row in that dim at all. Cube reaches school through
`student_school_enrollments` on the same key, so those rows already carry a null
location, region, and grade level today, and are invisible to any
location-scoped `access_policy` filter, because `location IN (...)` never
matches null. That is a pre-existing defect, tracked separately, and not
something this model should inherit.

The daily fact needs no school column. Cube's existing traversal is adequate for
day-level queries, and the snapshot gets school from upstream.

That gap is [#4803](https://github.com/TEAMSchools/teamster/issues/4803), a
sub-issue of the Focus modeling backlog
([#4985](https://github.com/TEAMSchools/teamster/issues/4985)). It reports 961
orphaned keys, essentially all Miami AY2025: #4775 made Focus the sole source of
Miami enrollment, and Focus dates a returning student's stint to the real first
day of school where PowerSchool used a July 1 rollover, so `entrydate` and
therefore the surrogate key differ. Sourcing the snapshot from upstream means
Miami AY2025 attendance is attributed to its schools correctly, which the
dimension path currently cannot do.

### Grain is student and school, not the enrollment stint

`student_enrollment_key` is keyed on entry date, so a student who exits and
re-enrolls at the same school becomes two stints with two separate
accumulations. In AY2025 that is **73 of 14,498 student-school pairs**.

That would break the eligibility rule above. A student with 6 membership days
before leaving and 6 after returning has 12 days at that school and is eligible,
but as two stints each falls under 10 and both are excluded.

So the snapshot aggregates across stints, keyed on `student_key` and
`location_key`. A student who attends two different schools in one year gets a
row per school, which is what every authority describes: the threshold applies
per school, not per district. 29 AY2025 students attended more than one school.

Compute `is_chronically_absent` from the accumulated counts rather than by
comparing the averaged float:

```sql
-- 198 AY2025 enrollments sit at exactly 90.0%. Comparing the float average
-- sorts 79 of them one way and 119 the other, on representation alone.
cumulative_present * 10 <= cumulative_membership * 9 as is_chronically_absent
```

### Materialize it as a table

Materialize as a table on a nightly cron, matching the two precedents in this
repo — `int_topline__ada_running_weekly` (#4153, midnight cron off the same
upstream) and `fct_assessment_scores_enrollment_scoped` (#4468, 5x/day because
Cube needs intra-day assessment freshness). Attendance needs nightly only: the
KIPP Foundation criteria require a nightly refresh and a visible refresh
timestamp, not intra-day.

```yaml
config:
  materialized: table
  meta:
    dagster:
      # Table, not the marts-default view: the kipptaf marts block sets only
      # +schema and +contract, and 7 of the 10 attendance-star models are
      # views in prod today, so a Cube query re-expands the whole chain.
      # That is the #4333 defect #4468 fixed for the assessment star.
      #
      # Cron, not eager: the upstreams are eager and would drive repeated
      # rebuilds of a 3.6M row model for freshness nobody consumes.
      #
      # 06:00 and 15:00 match the attendance dashboard's own measured
      # cadence, verified from 12 consecutive materializations. These are
      # LOCAL hours, not UTC — the dbt translator passes the code
      # location's LOCAL_TIMEZONE (America/New_York), so this is 6am and
      # 3pm Eastern.
      automation_condition:
        cron_schedule: 0 6,15 * * *
```

Eager is not the option here for the same reason it was not for assessments: the
upstreams are eager and would drive repeated rebuilds of a 3.6M row model for
freshness no consumer uses. The kipptaf `marts:` block in `dbt_project.yml` sets
only `+schema` and `+contract`, so a mart defaults to a view, and prod confirms
the consequence: `fct_student_attendance_daily`,
`fct_student_attendance_streaks`, and `dim_student_enrollments` are all views,
while `fct_assessment_scores_enrollment_scoped` is a table because
[#4468](https://github.com/TEAMSchools/teamster/pull/4468) materialized the
assessment star for Cube performance under
[#4333](https://github.com/TEAMSchools/teamster/issues/4333).

This also revises the performance claim earlier in this spec. The 38.4s and
51.6s Cube timings are substantially view re-expansion across the attendance
star, not the inherent cost of selecting a period-end row. Materializing that
star is a separate, cheaper fix with direct precedent, and it does not replace
this work — the definition defects and the 30-measure duplication are
independent of it — but it may deliver most of the speed benefit on its own.

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
snapshot. Both derive from `int_students__attendance_daily`, so they agree on
attendance values.

They do **not** agree on school attribution until
[#4803](https://github.com/TEAMSchools/teamster/issues/4803) is fixed. The
snapshot carries `schoolid` from upstream and attributes every stint; a
day-level query reaching school through `dim_student_enrollments` loses the 961
orphaned Miami AY2025 keys to a null location. So a per-school breakdown of the
daily fact and of the snapshot will differ for Miami AY2025. Document that on
the snapshot's properties file rather than papering over it.

## Enrollments that do not span the period

A student enrolled 1 September and withdrawn 10 October is the case that breaks
naive designs, and it is worth stating exactly.

- They get a **September row** and an **October row**. The October row's
  `period_end_date_key` is 10 October, their own last membership day, not the
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

## Truancy rides along; enrollment headcount does not

`queryRewrite`'s snapshot guard covers four measure stems on
`student_attendance` — `chronically_absent`, `tier_1_2`, `tier_3`, and `truant`
— and one on `student_enrollments`, `count_students`. Removing the block means
answering for all of them, not only chronic absence.

**Truancy moves to this snapshot.** Same fact, same grain, same anchor
semantics, so it needs one more column, `is_truant`, resolved at
`period_end_date_key`. The criteria stay regional and stay in
`int_students__attendance_daily` where they already are: Miami uses 15 or more
absences in a 90 day rolling window, the New Jersey regions use a projected 50
or more for the year. This model does not change that logic, only where the
period-end value is read from. That retires the 9 truancy measures in the three
anchor families.

**Enrollment headcount does not, and does not need a snapshot either.**
`student_enrollments.count_students` is `count_distinct` on
`student_school_enrollments.student_key` over the same fact. A distinct count is
idempotent, so a student appearing on 180 days still counts once — there is no
duplication to correct. The `cube.js` comment claiming an unanchored count
overcounts because a student "appears in N rows" states the wrong mechanism.

What actually differs is the metric. Unanchored, a date range returns every
student enrolled at any point in it; the measure is documented as a
point-in-time headcount. The anchor pins the as-of date.

Enrollment headcount has no cumulative accumulation — no year-to-date rate, no
eligibility threshold, no period-end value to reconstruct — so a snapshot is
disproportionate. Three named measures filtering flags the cube already exposes
as dimensions cover it:

| measure                    | filter                           |
| -------------------------- | -------------------------------- |
| `count_students_year_end`  | `is_current_record`              |
| `count_students_month_end` | `is_enrollment_month_end_record` |
| `count_students_week_end`  | `is_enrollment_week_end_record`  |

No dbt change, no new model. With those in place the `count_students` stem comes
out of the guard, and once the attendance stems go too the `queryRewrite`
snapshot block is empty and deletes cleanly.

## Documentation surfaces

Three places encode the anchor rules for consumers, and all three reach an LLM
through the Cube MCP's `meta` tool, so a stale one silently teaches the wrong
query.

1. **`student_attendance_view` description.** Its second paragraph documents the
   entire anchor contract: base measures defaulting to year-end, a single
   `date_day` equality filter for point-in-time, `_month_end` and `_week_end`
   for trends. Every sentence becomes wrong. Replace with routing — this view
   answers day-level questions, the snapshot answers rates as of a period.
1. **The new snapshot view's own description.** State that `period_type` selects
   the grain, that no anchor filter is needed or accepted, and that a row exists
   only for a period in which the enrollment had a membership day.
1. **The MCP `meta` docstring in `src/cube/mcp/server.py`.** It names the
   analyst-facing views by example and carries the grain and scope rules, but
   has no rule for choosing between two views of one domain. Add the new view to
   the examples and state the routing rule there, since that docstring reaches
   the model on every client.

Nothing else in `mcp/server.py` references anchors, snapshots, or chronic
absence, so there is nothing to remove there.

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
- A student with 6 membership days before exiting and 6 after re-enrolling at
  the same school is eligible, on 12 combined days.
- A student at two schools in one year gets one row per school per period, and
  each school's threshold is evaluated on that school's days alone.
- An enrollment at exactly 90.0% ADA is chronically absent AND in Tier 3, never
  Tier 2.
- Truancy at period end matches the current `_month_end` and `_week_end` truancy
  measures per region, since the regional criteria are unchanged.

Reconciliation against the figures on
[#4994](https://github.com/TEAMSchools/teamster/issues/4994): 11,153 counted
today, 180 leavers restored, 119 added at exactly 90.0%, 147 excluded under 10
days.

**Month and week DO move, and an earlier draft of this spec was wrong to predict
otherwise.** The anchor semantics genuinely do not move — the row population is
identical apart from the stint-months collapsed by combining re-enrollments, and
the leaver mechanism contributes exactly zero at month and week grain because
`is_month_end_record` already requires a membership day. What moves is the two
DEFINITION changes, which apply at every grain rather than only at the year:

| Grain | CA movement | Buckets moved | Unexplained |
| ----- | ----------- | ------------- | ----------- |
| month | -1,530      | 11 of 11      | 0           |
| week  | -3,493      | 44 of 44      | 0           |

Month attribution: -1,984 from cumulative eligibility, +437 from the exact-90.0%
fix, +17 from combined stints. Week: -5,159, +1,543, +123. Zero unexplained in
every bucket at both grains.

The concentration matters more than the totals. **The first month of school
collapses**: in 2025-08 only 1,317 of 10,513 enrollments are eligible, 12.5%,
because the 10-day threshold is cumulative. The rate barely moves, 19.49% to
18.53%, but the count falls 88%. That is arguably correct — a student cannot be
chronically absent on day five — but a month-over-month series then starts from
a denominator an eighth the size of the next point's. KIPP Foundation criteria
item 1 already requires displaying the number of students in each ADA and CA
calculation, which makes the small early denominator visible rather than
misleading; that requirement is what makes accepting this behaviour defensible.

**Decision: accept this behaviour.** No model change, no row suppression, no
extra flag. Three reasons. It is what New Jersey, Florida, and KIPP Foundation
all specify — a student cannot be chronically absent on day five. Every row
already carries `is_ca_eligible`, so a consumer can report eligible against
total without new columns. And KIPP Foundation criteria item 1 already requires
displaying the number of students in each ADA and CA calculation, so an August
count of 1,317 beside the rate reads as thin rather than broken.

What this obliges: the early-period behaviour must be documented where consumers
meet it — the snapshot view's description and the properties file — not left for
someone to rediscover from an August tile. That belongs with the other
documentation surfaces.

Two later months move on the exact-90.0% fix rather than eligibility: 2025-10 by
+1.20pp and 2026-06 by +2.07pp, because both tend to land cumulative membership
days on a multiple of 10, which is where an exact 9/10 ratio occurs.

## Out of scope

- The New Jersey 45-day figure
  ([#5015](https://github.com/TEAMSchools/teamster/issues/5015)).
- Pre-aggregations. At under 750K rows they may not be needed; measure first.
  The 55 second MCP deadline issue is real but separate.

## Open question for KIPP Foundation

Their criteria contradict themselves. Item 1 calls Tier 1 and Tier 2 on track at
90% or above ADA. Item 8 says chronic absence is ADA at or below 90.0%. A
student at exactly 90.0% is both.

We resolve it by starting Tier 2 strictly above 90.0%, so Tier 1 plus Tier 2
means not chronically absent. That deviates from their stated Tier 2 range of 90
to 94% for students sitting exactly on the line, 198 of them in AY2025. Ask them
which way they intend it before the figure is reported upward, because the
answer changes both the tier distribution and the chronic absence count.
