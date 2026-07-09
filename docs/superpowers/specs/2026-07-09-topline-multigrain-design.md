# Topline cascade dashboard: multi-grain aggregates

Issue: [#4363](https://github.com/TEAMSchools/teamster/issues/4363)

## Problem

`rpt_tableau__topline_cascade_dashboard` has two problems:

1. **Cost.** `int_topline__dashboard_aggregations` is a view. Six student-level
   GROUP BYs (three org levels × student/staff) plus goal range-joins over
   `int_topline__student_metrics` (student × week × indicator × layer, a large
   table) recompute on every Tableau extract refresh (daily 5am Dagster cron)
   and on any ad-hoc datasource touch.
2. **Grain.** The extract only produces week-grain aggregates (`term` =
   `week_start_monday`). Stakeholders need month, academic-quarter, and YTD
   views alongside weeks — displayable simultaneously in one dashboard.

## Semantic model

Weekly metric values come in two flavors, and a month/quarter/YTD value means
something different for each:

- **As-of metrics** — running or snapshot values where the weekly number already
  means "state of the world through this week" (ADA running, GPA, i-Ready
  proficiency, enrollment, retention, seats staffed, all staff metrics). A
  period's value is the value from the last complete week ending on or before
  the period's effective end.
- **Period-scoped metrics** — values stakeholders want recomputed within the
  period window with exact boundaries ("October ADA", "Q2 suspensions").

Which treatment applies is **per-indicator configuration**, not code
(stakeholder assignments will evolve).

## Design

### 1. Periods dimension — `int_topline__periods`

Grain: school × academic year × period. One row per:

- `week` — existing Mon–Sun weeks from `int_powerschool__calendar_week`
- `month` — exact calendar months clipped to the school's academic year
- `quarter` — reporting-term dates (`dim_terms` type `RT`, `Q1`–`Q4`, per school
  — already exact)
- `ytd` — one row, academic year start through year end

Columns: `period_type`, `period_start`, `period_end`, `period_label` (e.g.
`2026-W14` / `October` / `Q2` / `YTD`), `is_current_period`,
`is_most_recent_complete_period` (generalizing today's `is_current_week` and
`is_most_recent_complete_week`). In-progress periods are included ("November so
far"); the effective aggregation window end is
`least(period_end, current_date)`.

### 2. Per-indicator rollup config

New `period_rollup` column (`as_of` | `period`) on the existing topline
aggregate goals sheet (`stg_google_sheets__topline_aggregate_goals` →
`int_google_sheets__topline_aggregate_goals`), which already carries
per-indicator config (`aggregation_type`, `goal_direction`, `has_goal`, display
fields).

Proposed initial assignments:

- **`period`**: ADA, Chronic Absenteeism, Truancy, Suspensions, Successful
  Contacts, Chronic Absenteeism Interventions, i-Ready Lessons Passed, i-Ready
  Time on Task
- **`as_of`**: everything else (enrollment, GPA, proficiency snapshots, DIBELS,
  matriculation, retention, seats staffed, all staff metrics)

Flipping an indicator is a sheet edit, not a PR.

### 3. Tandem period-goals tab

Goals can differ by grain AND by period instance (e.g. ADA has per-month goals
plus an annual goal). Wide goal columns cannot express ramps, so goals get a
**long-format tab** on the same spreadsheet (new staging model
`stg_google_sheets__topline_period_goals`):

| Column          | Notes                                                                                            |
| --------------- | ------------------------------------------------------------------------------------------------ |
| entity keys     | same human-readable keys as the config sheet — `org_level`, entity, `schoolid`, layer, indicator |
| `academic_year` | nullable; blank = every year                                                                     |
| `period_type`   | `week` / `month` / `quarter` / `ytd`                                                             |
| `period_label`  | nullable; blank = every instance of the grain                                                    |
| `goal`          | the goal value                                                                                   |

**Resolution — most specific wins**, implemented as three explicit left joins
and `coalesce` (no window functions, per repo SQL conventions):

1. exact `period_type` + `period_label` (+ `academic_year`) match
2. `period_type` match with blank `period_label`
3. base `goal` from the config sheet (today's behavior)

The config sheet stays one row per indicator × entity (no duplication of config
columns); the base sheet remains year-agnostic. All goal math (`is_goal_met`,
`goal_difference_percent`, `progress_to_goal_pct`) runs off the resolved goal —
the formulas do not change.

### 4. Student-level metric rows at period grain

`int_topline__student_metrics` is rebuilt at grain student × **period** ×
indicator × layer, fed by two paths:

- **As-of indicators — no upstream changes.** Existing weekly models join to the
  periods dimension; each period takes the value from the last complete week
  ending on or before the period's effective end. Week-period rows are the
  weekly values themselves (today's behavior, unchanged).
- **Period-scoped indicators — period-grain variants.** Roughly 8 indicator
  models get a variant computed from their date-bearing source joined to the
  periods dimension on `date` within `period_start`..effective end (e.g. ADA
  from `int_powerschool__ps_adaadm_daily_ctod`, suspensions from incident dates,
  i-Ready lessons from lesson dates). Exact boundaries — no week-alignment fuzz.
  The `ytd` rows of these reproduce today's running values, which doubles as a
  reconciliation check.

### 5. One aggregation pass, materialized

`int_topline__dashboard_aggregations` keeps its current shape — three org-level
GROUP BYs each for student and staff metrics, goals join, goal math — but
grouped by `period_type` + period keys instead of week only, and becomes
**`materialized: table`** (set in properties yml). The daily Dagster rebuild
replaces per-refresh view recompute; this is the primary cost fix and more than
absorbs the ~4× row growth from added grains.

`rpt_tableau__topline_cascade_dashboard` stays a thin view: passthrough +
leadership crosswalk (its region decode is removed — see section 6), now
exposing `period_type` and `period_label`. `term` / `term_end` hold each
period's start/end so existing workbook fields keep resolving.

### 6. Region normalization (added after initial approval)

All topline models emit city-name regions (`Newark` / `Camden` / `Miami` /
`Paterson`, and `TAF` for central-office staff), replacing the mixed domain
where staff rows carried long ADP business-unit names
(`TEAM Academy Charter School`) that the extract only partially decoded —
central-office and Paterson staff currently leak long names into the extract's
region column.

- Mechanism: a shared `region_to_city` macro mapping business-unit names to the
  same values as `dim_regions.name` — NOT a join to `dim_regions`, which is a
  semantic-layer mart; no intermediate refs marts in this project, and this
  feature does not introduce the first such inversion.
- Applied in `int_topline__staff_metrics` and
  `int_topline__seats_staffed_weekly_aggregations` (the two long-form inputs).
  Student-side models already use city names.
- The goals staging models normalize `entity` (and the hash/display derivations)
  through the macro, so the sheet works in either form — the Ops edit moving
  `entity` to city names on Outstanding Teammates rows is non-blocking cleanup,
  and both goals tabs use only city names going forward. `aggregation_hash` /
  `aggregation_display` values change for staff region-level rows as a result.
- The periods dimension adds a `TAF` region-scope alias cloned from the
  org-scope windows (central office has no school calendar).
- The extract's region decode CASE is removed (passthrough); week-row regression
  comparisons must expect the region-value change on staff rows.

### 7. Tableau usage contract

Stacked long output: one datasource, multiple grains as rows. One dashboard can
show a weekly trend, a quarter scorecard, and a YTD headline simultaneously —
each worksheet filters `period_type`. **Every worksheet must filter
`period_type`**; an unfiltered aggregate mixes grains and double-counts.
Recommend a datasource-level default filter of `period_type = 'week'` that sheet
authors override deliberately.

## Testing & rollout

- **Regression**: `period_type = 'week'` rows must match current production
  output exactly (pre/post comparison query during development).
- **Reconciliation**: for period-scoped indicators, `ytd` rows must match the
  current running weekly values at the most recent complete week.
- **Uniqueness**: PK test on the aggregation table at (`metric_type`,
  `academic_year`, `org_level`, `region`, `schoolid`, `layer`, `indicator`,
  `discipline`, `aggregation_hash`, `period_type`, `term`) — `region` is the
  only discriminator on `org_level = 'region'` rows, where `schoolid` is null.
- **Rollout order**: sheet columns/tab added first (blank-safe: absent config
  defaults `period_rollup` to `as_of` and goals fall back to base `goal`), then
  dbt changes ship in one PR. The live workbook keeps functioning on week rows
  until the workbook adds grain filters.

## Out of scope

- Reworking the ~12 as-of weekly indicator models (reused as-is).
- Paterson (excluded upstream in `int_topline__student_metrics`).
- Changing the enrollment seat/budget target mechanism
  (`stg_google_sheets__topline_enrollment_targets` — annual, unchanged).
- Tableau workbook changes (handled by the dashboard owner once the extract
  carries the new columns).
