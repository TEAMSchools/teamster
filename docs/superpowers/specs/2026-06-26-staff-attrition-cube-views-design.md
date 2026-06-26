# Staff Attrition Cube Views — Design Spec

Issue: [#4275](https://github.com/TEAMSchools/teamster/issues/4275)

## Motivation

KTAF needs to analyze staff attrition in the Cube semantic layer: the attrition
rate for each methodology type, broken down by termination reason and by staff
characteristics (demographics, title, location, department, worker type) **as of
the time they left**, and tracked **over the course of the year** the way
`int_topline__staff_retention` tracks weekly retention.

The existing mart `fct_staff_attrition` is a final-outcome fact: one row per
`(employee, academic_year, attrition_type)`. It answers "did this person attrite
this year" but cannot express a cumulative attrition rate that climbs across the
year. It currently has **no downstream dbt model consumers** — the only
reference is the `cube.yml` exposure pre-wire — so a grain change is safe.

## Decisions

1. **Deliverables**: both a summary (aggregate rates) view and a detail
   (row-per-cohort-member) view, mirroring `staff_summary` / `staff_detail`.
2. **One period-grained fact**, not two. Refactor `fct_staff_attrition` to a
   daily-grained fact and **rename** to `fct_staff_attrition_daily`, mirroring
   `fct_student_attendance_daily`. The final-period row equals the end-of-year
   outcome, so one fact powers both the static rate and the trend.
3. **Period-end-snapshot grain with `is_*_record` anchor flags**, registered in
   `cube.js` `SNAPSHOT_CUBES`; the guard auto-injects the right period-end
   anchor by query granularity (mirrors attendance / enrollment). **Optimized**:
   only rows carrying at least one anchor flag are materialized (the daily spine
   is expanded transiently in-query to compute flags, then filtered away), so
   the Cube-facing table is roughly 6x smaller than true daily grain.
4. **As-of-exit characteristics resolved in dbt**: `work_location_key` FK to
   `dim_locations` (traverses to `dim_regions`) plus degenerate work-assignment
   attributes, all resolved as of the outcome-determination date. Demographics
   traverse `staff_status` (worker status) and `staff` (the staff dimension).
5. **Weekly is in scope** using ISO weeks (staff attrition is calendar-based,
   not PowerSchool school weeks). A `cube.js` change scopes the existing
   school-week rule to student cubes only.

## Key semantic difference from attendance / enrollment

In enrollment, a student leaves the daily fact at their exit date. For a
**cumulative attrition rate the denominator must stay fixed**: every cohort
member remains in the daily spine for the full window, and
`is_attrition_to_date` flips `0` to `1` once `termination_effective_date`
passes. An attritor who has already left is still counted in the denominator;
only the numerator grows. This mirrors the `is_retention` logic in
`int_topline__staff_retention`.

## dbt: `fct_staff_attrition_daily`

### Grain and keys

- Grain: one row per `(employee_number, academic_year, attrition_type, date)`
  across each type's cohort window, capped at `current_date`.
- Primary key `staff_attrition_daily_key` =
  `generate_surrogate_key(["employee_number", "academic_year", "attrition_type", "date_key"])`.
- The `(employee_number, academic_year, attrition_type)` tuple remains as a
  degenerate cohort grouping (no longer the PK).

### Cohort windows (unchanged methodology)

| Type            | Window start  | Window close        | Return check       |
| --------------- | ------------- | ------------------- | ------------------ |
| `foundation`    | `9/1` of year | `4/30` of year `+1` | `9/1` of year `+1` |
| `nj_compliance` | `7/1` of year | `6/30` of year `+1` | `7/1` of year `+1` |
| `recruitment`   | `9/1` of year | `8/31` of year `+1` | `9/1` of year `+1` |

Keep the existing cohort / returner / termination CTEs that produce one row per
`(employee, year, type)` with `is_attrition`, `termination_effective_date`,
`cutoff_date`, and `outcome_determination_date`. Cross each with a per-type date
spine:

```sql
generate_date_array(
  <window_start>,
  least(<window_close>, current_date('{{ var("local_timezone") }}')),
  interval 1 day
)
```

The daily spine is expanded only to compute the anchor flags; the final `SELECT`
keeps just the rows where at least one anchor flag is true (see the optimization
note in Decisions). The cumulative `is_attrition_to_date` is evaluated per
retained anchor day, so dropping in-between days loses nothing.

### Cumulative outcome flag

`is_attrition_to_date` (`INT64` 0/1) per spine day `d`:

- retained (`is_attrition` is false): always `0`
- attritor with a `termination_effective_date`: `1` when
  `termination_effective_date <= d`, else `0`
- attritor with a null `termination_effective_date`: `1` for the whole window
  (mirrors the topline null-term-date case)

### Anchor flags

All partitioned by `(employee_number, academic_year, attrition_type)` over the
spine:

- `is_current_record` — `d` equals the latest spine day (`<= today`). **Default
  anchor** (no grouping gives the as-of-now rate).
- `is_month_end_record` — `d` equals the `max` spine day within its calendar
  month (`date_trunc(d, month)`).
- `is_week_end_record` — `d` equals the `max` spine day within its ISO week
  (`date_trunc(d, week(monday))`, aligned to Cube's native
  `granularity:"week"`).
- `is_latest_record` — `d` equals the window-close day (final outcome; present
  only for completed years).

Each anchor is defined as `max(spine_day)` within its period partition, so a day
may carry several flags at once (a window-close that is also a month-end and a
week-end) and is materialized once.

### Period-boundary alignment

The window start/close dates (`9/1`, `4/30`, `6/30`, `8/31`) do not fall on ISO
week boundaries, but the `max`-within-partition definition handles this without
distortion:

- A partial first week anchors on the Sunday that closes it; a partial final
  week anchors on the **window-close date** (the spine is capped there, so it is
  the `max` spine day in that ISO week). Cube buckets that row into the ISO week
  containing the close date — correct, with no later row in the week to collide.
- All members of the same `(academic_year, type)` share one identical spine, so
  their week-end dates are identical and counts align cleanly within a type.
  Cross-type mixing in a single week bucket is already meaningless (different
  windows) and is guarded by the "filter to one `type`" usage note.
- Attrition is event-based, not a per-day rate, so partial first/last weeks
  carry no distortion — the cumulative count as of that boundary is exact. The
  only visible effect is that the first and last weekly points represent partial
  weeks.
- The three window-close dates are all calendar month-ends, so month granularity
  aligns exactly; only weekly has partial endpoints.

### Supported query granularities (consequence of the optimization)

Because only anchor rows are materialized, the fact has no arbitrary mid-period
days. Supported shapes: no date grouping (→ `is_current_record` as-of-now
snapshot, or a past year's final outcome when filtered by `academic_year`), and
`week` / `month` trends. **`day` granularity and single arbitrary-date pins are
not supported** — the `cube.js` guard errors on them for `staff_attrition` with
guidance, rather than silently returning a date with no anchor row.

### As-of-exit characteristics

Resolved as of `outcome_determination_date` (the same anchor the existing
`staff_status_key` FK uses), constant across the spine for each cohort row:

- `staff_key` — FK to `dim_staff`
  (`generate_surrogate_key(["employee_number"])`). Powers demographics and
  identity. New structural FK.
- `work_location_key` — FK to `dim_locations` (traverses to `dim_regions`),
  resolved from `dim_work_assignment_locations` for the primary assignment
  covering the determination date. Nullable; wrap with the
  `if(col is not null, generate_surrogate_key, cast(null as string))` pattern.
- Degenerate columns from the work-assignment SCD2 dims (primary assignment,
  intersection covering the determination date, same join shape as
  `staff_work_history` but pinned to one date): `position_title`, `job_code`,
  `department_name`, `business_unit_name`, `worker_type`,
  `is_management_position`, `full_time_equivalency`.
- Retained: `staff_status_key` FK, `termination_reason`,
  `termination_effective_date`, `type`, `cutoff_date`.

Coverage limitation is unchanged (ADP-only; pre-2021 NJ Dayforce staff excluded,
tracked at #3744) — work-assignment resolution may be null for those rows.

### Tests

- `staff_attrition_daily_key`: `unique`, `not_null`.
- Anchor-existence + one-per-period singular tests mirroring the
  `fct_student_attendance_daily__*_anchor_exists` / `__one_*_per_*` suite: at
  least one `is_current_record` per cohort tuple, one `is_month_end_record` per
  cohort-month, one `is_week_end_record` per cohort-ISO-week.
- `relationships` FKs to `dim_dates` (`date_key`), `dim_locations`
  (`work_location_key`), `dim_staff` (`staff_key`), `dim_staff_status`
  (`staff_status_key`).
- `foreign_key` constraints declared on each FK column (feeds the marts
  reference diagram).

### Rename mechanics

- Rename the model file and `properties` yml to `fct_staff_attrition_daily`.
- Update `cube.yml` exposure `depends_on` ref (line 67).
- Grep `fct_staff_attrition` across `*.sql`, `*.yml`, `*.md` to catch
  stragglers.

## Cube: cubes (`src/cube/model/cubes/staff/`)

### `staff_attrition`

`public: false`, `sql_table: kipptaf_marts.fct_staff_attrition_daily`. Joins
(all `many_to_one`, one FK route each — no diamond to `staff`):

- `dates` on `date_key`
- `staff` on `staff_key` — demographics + identity
- `locations` on `work_location_key` — location, traverses to `regions`
- `staff_status` on `staff_status_key` — `status_name` only; this cube does
  **not** re-join `staff` (avoids a diamond to `staff`)

Dimensions: the four anchor flags, plus `type`, `termination_reason`,
`position_title`, `job_code`, `department_name`, `business_unit_name`,
`worker_type`, `is_management_position`, `full_time_equivalency`,
`termination_effective_date`, `is_attrition_to_date`.

Measures (all `count_distinct(staff_key)` based, anchor-guarded):

- `count_cohort` — `count_distinct(staff_key)`. Denominator.
- `count_attritors` — `count_distinct(staff_key)` filtered
  `is_attrition_to_date = 1`.
- `attrition_rate` — `count_attritors / count_cohort`.
- `retention_rate` — `1 - attrition_rate`.

### `staff_status` (new minimal cube)

`public: false`, `sql_table: kipptaf_marts.dim_staff_status`. Exposes
`staff_status_key` (PK) and `status_name`. No join to `staff`.

## Cube: views (`src/cube/model/views/staff/`)

### `staff_attrition_summary`

Aggregate rates and breakdowns — no direct identifiers. Members: the four
measures; `type`, `termination_reason`, work-assignment dims (`position_title`,
`department_name`, `worker_type`, `is_management_position`),
`staff_status.status_name`; demographics (`gender_identity`, `race`,
`is_hispanic`) as aggregate breakdowns; `locations` + `regions` descriptors;
`dates` (`academic_year`, `month_name`, `month_number`, `year_number`,
`date_day`) and the anchor dims. Folders group dimensions (Attrition, Date,
Location, Staff, Status). Single `cube-access-staff-data` policy,
`includes: "*"` (no PII tier — aggregate demographics only; low-n suppression
tracked at #4237).

### `staff_attrition_detail`

Row-level, one row per cohort member when anchor-filtered. Members: staff
identity (`staff_key`, `staff_unique_id`, `full_name`, `first_name`,
`last_name`, work/google email, AD username), demographics + DOB,
`termination_reason`, `termination_effective_date`, `is_attrition_to_date`,
work-assignment exit traits, `status_name`, location/region, dates. Two-tier
access policy mirroring `staff_detail`:

- `cube-access-staff-data` `includes: "*"`, `excludes:` `personal_email`,
  `personal_cell_phone`, `birth_date`, `gender_identity`, `race`, `is_hispanic`.
- `cube-access-staff-pii` `includes: "*"`.

Both views: usage notes in `description:` instruct filtering to a single `type`
(otherwise the three methodologies blend), explain that the current/as-of rate
comes from omitting the date grouping (optionally filtered by `academic_year`
for a past year's final outcome) and the trend from grouping a `week` / `month`
granularity (the anchor guard handles the snapshot), and note that `day`
granularity and arbitrary single-date pins are not supported.

## `cube.js` snapshot-guard registration

Drafted as a code block for manual application (security-model file).

- `SNAPSHOT_CUBES`: append `"staff_attrition"`.
- `SNAPSHOT_MEASURE_STEMS.staff_attrition`:
  `["count_cohort", "count_attritors", "attrition_rate", "retention_rate"]`.
- `SNAPSHOT_ANCHOR_OVERRIDES.staff_attrition`:
  `{ default: "is_current_record" }`.
- New `SNAPSHOT_SCHOOL_WEEK_CUBES` set =
  `{ "student_attendance", "student_enrollments" }`. In the guard loop, derive
  `usesSchoolWeek = SNAPSHOT_SCHOOL_WEEK_CUBES.has(cubePrefix)`; only compute
  `groupsBySchoolWeek` and throw on ISO `granularity:"week"` when
  `usesSchoolWeek`. For calendar cubes, `period = granularity`, so
  `granularity:"week"` maps to `is_week_end_record`. Update the `_week_end`
  named-measure `ok` check to accept `granularity === "week"` for
  non-school-week cubes (no staff `_week_end` named measures exist yet, but keep
  it correct).
- New `SNAPSHOT_ANCHOR_ONLY_CUBES` set = `{ "staff_attrition" }` (cubes whose
  fact materializes only anchor rows, so arbitrary days have no row). For these,
  the guard errors on `granularity:"day"` and on a single arbitrary-date pin
  (single-element `dateRange`, equal-bounds range, or a `dates_date_day`
  dimension / equals filter), directing users to omit the date for the current
  snapshot or use `week` / `month`. This replaces, for these cubes, the day-pin
  "already anchored" branch that assumes a daily row exists.

## Exposures / contracts

- The `cube.yml` exposure already lists the fact (rename the ref). Add the new
  views to the Cube exposure surface as appropriate.
- Confirm the marts FK-constraint and uniqueness conventions
  (`src/dbt/kipptaf/models/marts/CLAUDE.md`) are satisfied on the new fact.

## Validation plan

- Build the fact in a dev schema; verify PK uniqueness and FK population
  (`countif(<fk> is null)` < 1%).
- Reconcile a completed-year static rate (anchor = `is_current_record`, single
  `type`) against the prior final-outcome `fct_staff_attrition` numbers.
- Spot-check the monthly and weekly trend: cumulative `count_attritors` is
  monotonically non-decreasing across periods and equals the final-outcome count
  at the last period.
- Validate the snapshot guard: a year / month / week query auto-anchors;
  `attrition_rate` without a date pin returns the as-of-now rate; an ISO-week
  staff query no longer throws the school-week error.

## Open items / risks

- **Materialized fan-out**: anchor rows only — roughly staff x 3 types x (~52
  week-ends + ~12 month-ends, deduped) x history years, about 6x smaller than
  true daily. The transient daily expansion is a build-time compute cost, not a
  stored one. Tradeoff: no `day`-granularity or arbitrary single-date queries
  (guard-enforced; see "Supported query granularities").
- **Null work-assignment resolution** for pre-2021 Dayforce staff (#3744) — FKs
  are nullable by design.
