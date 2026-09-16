# GPA snapshot cadence — design

Refs [#5218](https://github.com/TEAMSchools/teamster/issues/5218). Parent
[#5212](https://github.com/TEAMSchools/teamster/issues/5212).

## Problem

`snapshot_powerschool__gpa_term` and `snapshot_powerschool__gpa_cumulative` each
run a `MERGE` roughly every 10 minutes. Measured over the 24 hours ending
2026-09-16 in `JOBS_BY_PROJECT`:

| Snapshot                               | `MERGE` jobs | Slot hours |
| -------------------------------------- | ------------ | ---------- |
| `snapshot_powerschool__gpa_cumulative` | 147          | 2.23       |
| `snapshot_powerschool__gpa_term`       | 138          | 3.90       |

Together that is 6.13 slot hours a day, which matches the 40 slot hours over 7
days reported on the issue.

Each merge is cheap. The cadence is the cost.

## Why the cadence is that high

Neither snapshot declares an automation condition, so
`CustomDagsterDbtTranslator.get_automation_condition` falls through to
`dbt_table_automation_condition()` — a dbt snapshot's `config.materialized` is
`snapshot`, not `view` or `ephemeral`, so it takes the table branch.

That condition includes `_build_any_ancestor_updated(view_selection=...)`, which
recurses through view chains to the nearest table boundary. Both snapshots sit
on top of non-table upstreams:

- `int_powerschool__gpa_term_current` is `materialized: ephemeral`.
- `int_powerschool__gpa_cumulative` is a view (no materialization override).

So every PowerSchool grade or gradebook table refresh upstream of those views
propagates a materialization request to the snapshot. `int_students__gpa`'s
properties YAML already records this churn as a known cost from
[#5082](https://github.com/TEAMSchools/teamster/issues/5082).

## Decision

Put both snapshots on `dbt_cron_automation_condition()` at `0 23 * * *` by
adding `meta.dagster.automation_condition.cron_schedule` to each snapshot's
existing `config.meta.dagster` block in
`src/dbt/kipptaf/snapshots/powerschool.yml`.

```yaml
automation_condition:
  cron_schedule: 0 23 * * *
```

The key goes above `asset_key`, matching the key order in
`src/dbt/kipptaf/snapshots/students.yml` and
`src/dbt/kipptaf/snapshots/kippadb.yml`, which took the same change in
[#4821](https://github.com/TEAMSchools/teamster/issues/4821).

No SQL and no Python changes. The translator already routes a snapshot node down
the cron branch, and `cron_timezone` defaults to the code location's
`LOCAL_TIMEZONE`, which is `America/New_York` for kipptaf.

## Why 23:00 and not the precedent's midnight

Every consumer resolves the snapshot at day grain:

- `int_topline__gpa_term_weekly` and `int_topline__gpa_cumulative_weekly` cast
  `dbt_valid_from` to a date, deduplicate on `dbt_valid_from_date`, then join
  `week_start_monday between dbt_valid_from_date and dbt_valid_to_date`.
- `int_powerschool__gpa_term_lookback` matches versions against the first
  instant of the day after `current_date - N`, for N of 7, 14, and 28.

A GPA change stored at 14:00 on a Monday today lands `dbt_valid_from_date` =
that Monday. Captured at 23:00 the same day, it still does. Captured at 00:00
the next day, it lands on Tuesday instead, shifting every topline weekly value
and every lookback column by one day.

The two topline models tick at `0 0 * * *` and the `student_course_grades`
Tableau exposure refreshes at `0 4 * * *`, so a 23:00 capture is upstream of
both.

There is no dependency-ordering concern to solve by sharing a consumer's tick.
The snapshot's upstreams are a view and an ephemeral model, which the view
automation condition re-runs only on code change, so at the cron tick the
snapshot reads live views over the current PowerSchool tables.

## Accepted loss

Roughly 100 capture instants a day collapse to one. A grade stored and then
revised the same day keeps only the end-of-day value; the intermediate value is
lost permanently.

This differs from the #4821 precedent, where the two snapshots had captured no
change in hundreds of executions. These capture 15,000 to 20,000 row-versions a
day. The history is real — it is just history no consumer reads, because all
three consumers resolve at day grain. A repo-wide search found no Cube file and
no other surface reading either snapshot.

## Alternatives considered

**Cron at `0 0 * * *`.** Matches the #4821 precedent exactly and shares the
topline tick. Rejected: it shifts day attribution for all three consumers, as
above.

**Flip `int_powerschool__gpa_cumulative` and `int_powerschool__gpa_term_current`
to cron tables.** This would cut the churn at its source rather than at the
snapshot. Rejected as out of scope for #5218: `int_powerschool__gpa_cumulative`
is a shared source-package view with consumers beyond these two snapshots, so
the blast radius is much wider than the issue covers.

## Verification

Pre-merge, there is nothing to build — a properties-only change fires no
`code_version_changed`, so `dbt build` proves nothing about cadence. Confirm
`dbt parse` succeeds and the manifest carries the new meta key.

Post-merge, after the first tick:

1. `MERGE` count per day for both tables in `JOBS_BY_PROJECT` drops to about 1
   each, from 147 and 138.
2. `dbt_valid_from` still carries a version on every day a grade store occurred
   — the day-level gaps the consumers read are unchanged.
3. `int_powerschool__gpa_term_lookback` still returns non-null
   `gpa_y1_1_week_prior`, `gpa_y1_2_week_prior`, and `gpa_y1_4_week_prior` for
   the expected population.

A properties-YAML-only change does not fire `code_version_changed` at deploy, so
the relation does not rebuild until the first cron tick. Do not judge the deploy
by BigQuery object state before 23:00 local.
