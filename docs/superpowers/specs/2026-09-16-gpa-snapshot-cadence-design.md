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
recurses through view chains to the nearest table boundary, plus a plain
`any_deps_updated()` check against direct dependencies regardless of their
materialization.

- `int_powerschool__gpa_term_current` is `materialized: ephemeral`, so
  `snapshot_powerschool__gpa_term`'s ancestor-updated recursion reaches every
  PowerSchool grade table upstream of it.
- `int_powerschool__gpa_cumulative` is `materialized: table` in its
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/` YAML — not a
  view. (`ref()` resolves to the kipptaf project's own copy of this model name,
  not the source-system package's; see kipptaf CLAUDE.md.) Its churn instead
  comes from plain `any_deps_updated()` firing on that table's own eager
  rebuilds.

So every PowerSchool grade or gradebook table refresh upstream of
`int_powerschool__gpa_term_current` propagates a materialization request to
`snapshot_powerschool__gpa_term` directly, and every rebuild of
`int_powerschool__gpa_cumulative` itself propagates one to
`snapshot_powerschool__gpa_cumulative`. `int_students__gpa`'s properties YAML
already records this churn as a known cost from
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

No Python changes. The translator already routes a snapshot node down the cron
branch, and `cron_timezone` defaults to the code location's `LOCAL_TIMEZONE`,
which is `America/New_York` for kipptaf. This PR does make one small SQL change
alongside the cadence change — see "Why 23:00..." and "Accepted loss" below.

## Why 23:00 and not the precedent's midnight

The two topline models (`int_topline__gpa_term_weekly` and
`int_topline__gpa_cumulative_weekly`) cast `dbt_valid_from` and `dbt_valid_to`
to a date and dedupe/join on it. `cast(timestamp as date)` truncates in UTC on
BigQuery, not local time: a GPA change stored at 23:00 ET on a Monday casts to
2026-09-15 — Tuesday, not Monday — the same UTC day a midnight capture would
land on. 23:00 does **not** preserve day attribution over a midnight capture for
these two models; a bare cast lands both on the same UTC-truncated day. This
change fixes that directly rather than accepting it: both models now derive the
date with `date(dbt_valid_from, '{{ var("local_timezone") }}')` instead of a
bare cast (see "Accepted loss" below), which makes their day attribution correct
at any cron hour and removes the cadence sensitivity entirely.

The actual reason for 23:00 over 00:00 is `int_powerschool__gpa_term_lookback`,
which matches snapshot versions against the first instant of the day after
`current_date - N`, in local time, for N of 7, 14, and 28 — a local-midnight
boundary. A 23:00 local capture clears that boundary with an hour of margin. A
00:00 local capture lands just past the boundary instant and, on sub-second
run-start timing, can resolve one day stale.

The two topline models tick at `0 0 * * *` and the `student_course_grades`
Tableau exposure refreshes at `0 4 * * *`, so a 23:00 capture is upstream of
both regardless.

There is no dependency-ordering concern to solve by sharing a consumer's tick.
`int_powerschool__gpa_term_current` is ephemeral and inlines into the snapshot's
own query, so `snapshot_powerschool__gpa_term` reads a live view over the
current PowerSchool tables at the cron tick. `int_powerschool__gpa_cumulative`
is a table that refreshes on its own eager automation condition through the day,
so `snapshot_powerschool__gpa_cumulative` reads whatever that table's last
materialization holds at 23:00 — in practice current, since the table rebuilds
on every upstream change, but not itself a live view read.

## Accepted loss

Roughly 100 capture instants a day collapse to one. A grade stored and then
revised the same day keeps only the end-of-day value; the intermediate value is
lost permanently.

This differs from the #4821 precedent, where the two snapshots had captured no
change in hundreds of executions. These capture 15,000 to 20,000 row-versions a
day. The history is real — it is just history no consumer reads, because all
three consumers resolve at day grain. A repo-wide search found no Cube file and
no other surface reading either snapshot.

Under a 23:00 tick, the lookback no longer sees a change stored between 23:00
and local midnight — that change lands on the next day's capture instead. Small,
and an acceptable trade for the hour of margin against the lookback's boundary.

The topline models' `dbt_valid_from`/`dbt_valid_to` → date derivation was a bare
`cast(... as date)`, which truncates in UTC and does not actually match a 23:00
capture to the correct local day (see "Why 23:00..." above) — a latent bug, not
something this design accepted. This change fixes it directly in this PR: both
models now derive the date with
`date(dbt_valid_from, '{{ var("local_timezone") }}')`, so it is corrected here,
not deferred to a later change.

## Alternatives considered

**Cron at `0 0 * * *`.** Matches the #4821 precedent exactly and shares the
topline tick. Rejected: it removes the hour of margin
`int_powerschool__gpa_term_lookback` needs against its local-midnight boundary
(see "Why 23:00..." above). It has no effect on the topline models' day
attribution once this PR's date-derivation fix lands.

**Flip `int_powerschool__gpa_term_current` to a cron table (and put
`int_powerschool__gpa_cumulative` on the same condition).** This would cut the
churn at its source rather than at the snapshot. Rejected as out of scope for
#5218: both are shared models with consumers beyond these two snapshots, so the
blast radius is much wider than the issue covers.

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
