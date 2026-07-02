# GPA term lookback intermediate — design

Issue: [#4315](https://github.com/TEAMSchools/teamster/issues/4315)

## Problem

Stakeholder request for the gradebook dashboard rebuild: for each student, show
— relative to the current day — what their Y1 weighted GPA was one week earlier,
two weeks earlier, and four weeks earlier. Lookbacks cross term boundaries when
necessary but never cross academic years.

No model provides this today. `int_topline__gpa_term_weekly` is the nearest
relative, but it is Monday-anchored (value during a calendar week), not
relative-to-today, and it lives in the topline domain with an enrollment-weeks
dependency this ask doesn't need.

## Source of truth

`snapshot_powerschool__gpa_term` (kipptaf, `snapshots/powerschool.yml`) is a
check-strategy snapshot of `int_powerschool__gpa_term_current` — the
`is_current` term row per student-year:

- Unique key: `_dbt_source_relation`, `studentid`, `yearid`, `schoolid` —
  mirrors the `int_powerschool__gpa_term` grain, where a mid-year transfer
  carries separate GPA rows per school. The lookback model inherits `schoolid`
  for the same reason.
- Check columns: `gpa_y1`, `gpa_y1_unweighted`, `n_failing_y1`.
- `dbt_valid_to_current: '9999-12-31'` — open rows carry a far-future timestamp,
  not NULL.
- Capture is continuous: a new version row is added whenever a check column
  changes, so validity windows tile time with no gaps or overlaps per key.

Because the snapshot tracks the _current-term_ row, term crossings are inherent
— a lookback within the same `yearid` reads whichever term was current at that
instant. And because `yearid` is in the key, a lookback date that precedes the
year's first snapshot version finds no row and returns NULL, which is exactly
the never-cross-academic-years behavior.

## Why not `int_powerschool__gpa_term`

Two blockers, one decisive:

1. **DAG cycle.** The snapshot reads `int_powerschool__gpa_term_current`, which
   reads `int_powerschool__gpa_term`. A snapshot-derived column on
   `int_powerschool__gpa_term` would make the graph circular; dbt rejects it.
   The district-package model of the same name is further upstream still and
   cannot see a kipptaf snapshot at all.
2. **Grain mismatch.** Lookback values are year-grain (the snapshot key has no
   term); `int_powerschool__gpa_term` is term-grain. The columns would duplicate
   across every term row.

## Design

One new model: `int_powerschool__gpa_term_lookback` in
`src/dbt/kipptaf/models/powerschool/intermediate/`, plus a properties yml.

### Inputs

`snapshot_powerschool__gpa_term` only, filtered to the current year:
`yearid = {{ var("current_academic_year") - 1990 }}` — and to production
district relations
(`regexp_contains(_dbt_source_relation, r'kipp[a-z]+_powerschool')` on the
dataset segment). The prod snapshot contains ~55k permanently-open ghost rows
whose `_dbt_source_relation` points at dev datasets (`zz_cbini_*`, injected
2025-12-03); without the filter they duplicate the grain per district after
`union_dataset_join_clause` prefix extraction. Cleanup tracked in
[#4318](https://github.com/TEAMSchools/teamster/issues/4318).

### As-of logic

For `weeks_prior` in `unnest([1, 2, 4])`, the as-of boundary is the first
instant of the day AFTER `current_date(local_timezone) - weeks_prior * 7` days,
converted to a UTC timestamp — i.e. "the value in effect at the end of that day,
local time":

- A snapshot version is in effect at the boundary when
  `dbt_valid_from < boundary and dbt_valid_to >= boundary`.
- Validity windows are non-overlapping per key, so each (student, school,
  lookback) matches at most one version. No deduplication, no `qualify`.
- End-of-day semantics absorb multiple intra-day versions by taking the last
  one, and are stable regardless of what time of day the consumer queries.

Conditional aggregation (`max(if(weeks_prior = N, <col>, null))` grouped by the
grain) pivots the three matches wide.

### Output

Grain: (`_dbt_source_relation`, `studentid`, `schoolid`) — one row per
student-school, current academic year only. `yearid` carried as a convenience
join column.

Nine measure columns — each check column at each lookback:

- `gpa_y1_1_week_prior`, `gpa_y1_2_week_prior`, `gpa_y1_4_week_prior`
- `gpa_y1_unweighted_1_week_prior`, `gpa_y1_unweighted_2_week_prior`,
  `gpa_y1_unweighted_4_week_prior`
- `n_failing_y1_1_week_prior`, `n_failing_y1_2_week_prior`,
  `n_failing_y1_4_week_prior`

NULL semantics: a lookback whose boundary predates the key's first snapshot
version is NULL. A student-school whose versions match none of the three
boundaries has no row at all; consumers left-join, so that is equivalent to an
all-NULL row.

### Materialization

View. "Relative to the current day" then resolves at query time — freshness
never depends on a rebuild schedule. No `materialized:` override needed (kipptaf
intermediate default is view).

### Consumer

The rebuilt gradebook rpt view left-joins on (`studentid`, `schoolid`, `yearid`)
plus the union-dataset join clause — same shape as
`rpt_tableau__gradebook_gpa`'s existing year-grain `gty` join. Wiring the
consumer is part of the dashboard-rebuild work, not this change.

## Testing

- `dbt_utils.unique_combination_of_columns` on (`_dbt_source_relation`,
  `studentid`, `schoolid`).
- Unit test mocking the snapshot with `format: sql` fixtures whose validity
  timestamps are built from `current_date` arithmetic (e.g.
  `timestamp(date_sub(current_date, interval 10 day))`), so the moving "today"
  is inside the fixture. Cases:
  1. Value changed between lookbacks — three different values surface.
  2. Version boundary exactly on a lookback day — end-of-day rule picks the
     later version.
  3. First snapshot version newer than the 4-week boundary — 4-week column NULL,
     1-week populated.
  4. Prior-year row — excluded entirely.

## Validation (prod, plan step)

- Confirm snapshot capture cadence and history depth (how far back
  `dbt_valid_from` goes) — determines when the 4-week tile first fills in.
- Spot-check a handful of student-school rows where the 1-week value differs
  from today's `gpa_y1`, verifying each against raw snapshot history. Aggregates
  only on any PR surface.

## Known edges (accepted)

- Check-strategy snapshots never close a row when it disappears from the source:
  a withdrawn student's last version stays open, so their lookbacks return
  last-known values. Enrollment scoping is the consumer's job (all gradebook
  views join from enrollments). Noted in the model description.
- Values reflect the snapshot capture that preceded the boundary — if the
  snapshot job skips a day, the lookback reads the last captured value, the same
  way any point-in-time read of this snapshot would.

## Out of scope

- The rebuilt gradebook rpt view (consumer).
- Any change to `int_powerschool__gpa_term`,
  `int_powerschool__gpa_term_current`, or the snapshot definition.
- Additional lookback horizons or measures beyond the nine columns above.
