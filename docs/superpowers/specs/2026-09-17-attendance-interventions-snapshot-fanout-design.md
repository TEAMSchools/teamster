# Attendance interventions snapshot fan-out — design

Refs [#5381](https://github.com/TEAMSchools/teamster/issues/5381).

## Problem

`int_topline__attendance_interventions_weekly` returns up to 354 rows for a
single student-week. `int_topline__student_metrics` reads it at student-week
grain and scores each row's `successful_call_count` / `total_anticipated_calls`
pair, so a student with 354 rows weighs 354 times as much as a student with one.

Measured against prod on 2026-09-17: 422,821 of 809,706 student-week keys are
duplicated.

Three independent causes.

### 1. The snapshot never closes a version

`snapshot_students__attendance_interventions_rollup` declares
`unique_key: [student_number, academic_year, schoolid]`. `schoolid` is NULL in
255,662 of 264,910 rows of `int_students__attendance_interventions`, because it
comes from `lc.powerschool_school_id` — reached through the comm-log left join,
so it resolves only for students who had a completed call.

dbt's `unique_key_join_on` compiles a composite key to plain equality per
column, and NULL never equals NULL. So `snapshotted_data` never matches the
source:

- `updates_source_data` inner-joins on that key, finds nothing, and closes no
  version.
- `insertions_source_data` left-joins on it, sees NULL, and inserts a new row
  every run.

Result: 24,026,270 of 24,045,900 rows sit open at `9999-12-31`, one key holds
6,971 concurrent open versions, and every row carries a distinct
`dbt_valid_from`. The weekly model's
`week_start_monday between dbt_valid_from_date and dbt_valid_to_date` then
matches all 354 distinct `dbt_valid_from` dates at once.

The other kipptaf snapshots are healthy — `powerschool__gpa_term` sits at 2.8%
open, `iready__instructional_usage_data` at 0.9%.

### 2. `schoolid` tears the numerator from the denominator

`int_students__attendance_interventions_rollup` groups by `schoolid`, so a
student whose rows carry a mix of NULL and populated `schoolid` splits into 2
rows. `successful_call_count` lands on one and part of `total_anticipated_calls`
on the other. 63 of 918 AY2026 student-years are torn this way; 7 AY2025
student-years split across 2 distinct schools instead.

`schoolid` is not part of the grain. `int_students__attendance_interventions`
holds exactly one row per `(student_number, academic_year, commlog_reason)` in
all 23 academic years — the `comm_log` CTE already dedupes on
`student_school_id, academic_year, reason`, and `int_people__location_crosswalk`
maps 25 distinct `location_deanslist_school_id` values to at most 1 PowerSchool
id each, so neither join fans out.

### 3. The weekly join omits `academic_year`

The join predicate is `on co.student_number = ca.student_number` alone. A
student with snapshot rows in both AY2025 and AY2026 matches a week in either
year. This is a live second fan-out, independent of causes 1 and 2.

## Design

### `int_students__attendance_interventions_rollup`

Drop `schoolid` from the select list and the `group by`. Grain becomes
`student_number, academic_year`.

Nothing downstream reads the column. The rollup is ephemeral and its only
consumer is the snapshot; the snapshot's only consumer is the weekly model,
which never selects `schoolid`. `rpt_tableau__attendance_interventions` and
`fct_student_attendance_interventions` read
`int_students__attendance_interventions` directly, not the rollup, and are
unaffected.

Collapsing merges exactly 2 cases, both correct:

| Case                            | Scale                   | Effect of collapsing                                    |
| ------------------------------- | ----------------------- | ------------------------------------------------------- |
| NULL vs populated `schoolid`    | 63 AY2026 student-years | Rejoins `successful_call_count` to its own denominator  |
| 2 distinct non-null `schoolid`s | 7 AY2025 student-years  | Sums a mid-year transfer's calls across both DL schools |

### `snapshots/students.yml`

`unique_key: [student_number, academic_year]`. Carry a short comment naming why
`schoolid` is not a key column, so it does not get re-added.

### `int_topline__attendance_interventions_weekly`

Mirror the pattern `int_topline__gpa_term_weekly` uses on
`cbini/fix/claude-topline-gpa-weekly-fanout`, which itself follows
`int_powerschool__gpa_term_lookback`:

- Delete the `deduplicate` CTE and both `cast(... as date)` columns. A
  contiguous snapshot needs neither.
- Add an `enrollment_weeks` CTE holding the model's `where` filters and
  `timestamp(date_add(week_end_sunday, interval 1 day), '{{ var("local_timezone") }}') as week_end_boundary`
  — the first instant of the day after the week closes, local.
- Reference the snapshot directly in the join rather than through a pass-through
  import CTE, which `.claude/rules/dbt-sql.md` bans.
- Join on `student_number`, `academic_year`, and the boundary compared half-open
  against the raw timestamps:
  `co.week_end_boundary > ai.dbt_valid_from and co.week_end_boundary <= ai.dbt_valid_to`.

The end-of-week anchor matches what #5375 settled on for the 2 GPA models, so
every topline weekly model agrees on what a week means.

Contiguity holds by construction after the repair below: `dbt_valid_to` is the
next version's `dbt_valid_from`, so a boundary equal to a version's
`dbt_valid_from` fails `boundary > dbt_valid_from` on that version and satisfies
`boundary <= dbt_valid_to` on the previous one. Exactly one version matches.

Weeks before a key's first `dbt_valid_from` match nothing and yield NULL.
`int_topline__student_metrics` already filters
`where total_anticipated_calls is not null`, so they drop out of the indicator.

### `properties/int_topline__attendance_interventions_weekly.yml`

Add `dbt_utils.unique_combination_of_columns` on `student_number`,
`academic_year`, `week_start_monday` at `config: severity: error`. The kipptaf
project default is `warn`, which would not fail CI, and this is a silent
double-count defect.

Add model and column descriptions, matching the GPA models' properties. Keep the
existing `materialized: table` and `cron_schedule: 0 0 * * *` config untouched.

## Snapshot table repair

The code change alone does not fix the data: the 24M open rows stay open, and
once the rollup stops emitting `schoolid` a snapshot run fails on the column
mismatch. One `CREATE OR REPLACE` repairs both. Charlie runs it — the BigQuery
MCP is SELECT-only and `bq` credentials expire mid-session.

`--full-refresh` is not an option here: `.claude/rules/dbt-models.md` prohibits
it on a snapshot, and it would flatten the topline weekly series back to the
start of the year. The rebuild below keeps 13 months of real history, taking
24,045,900 rows to 85,545 across 11,426 keys.

```sql
create or replace table
    `teamster-332318.kipptaf_students.snapshot_students__attendance_interventions_rollup` as

with
    collapsed as (
        select
            student_number,
            academic_year,
            dbt_valid_from,

            max(dbt_scd_id) as dbt_scd_id,
            max(dbt_updated_at) as dbt_updated_at,
            sum(successful_call_count) as successful_call_count,
            sum(total_anticipated_calls) as total_anticipated_calls,
        from
            `teamster-332318.kipptaf_students.snapshot_students__attendance_interventions_rollup`
        group by student_number, academic_year, dbt_valid_from
    ),

    flagged as (
        select
            *,

            format(
                '%T|%T', successful_call_count, total_anticipated_calls
            ) as current_values,

            lag(
                format('%T|%T', successful_call_count, total_anticipated_calls)
            ) over (
                partition by student_number, academic_year order by dbt_valid_from
            ) as prior_values,
        from collapsed
    ),

    boundaries as (
        select *
        from flagged
        where prior_values is null or prior_values != current_values
    )

select
    student_number,
    academic_year,
    successful_call_count,
    total_anticipated_calls,
    dbt_scd_id,
    dbt_updated_at,
    dbt_valid_from,

    safe_divide(
        successful_call_count, total_anticipated_calls
    ) as pct_interventions_complete,

    coalesce(
        lead(dbt_valid_from) over (
            partition by student_number, academic_year order by dbt_valid_from
        ),
        timestamp('9999-12-31')
    ) as dbt_valid_to,
from boundaries
```

What each part does:

- `collapsed` merges the `schoolid` split. `successful_call_count` is a `sum`
  and `total_anticipated_calls` is a `count`, so both add across the split rows.
  `dbt_scd_id` is only a match handle for dbt's merge, so `max` of 2 already
  unique values stays unique per group.
- `boundaries` keeps a row only where the value tuple changed from the previous
  `dbt_valid_from` — the versions a correctly-behaving snapshot would have
  written.
- `pct_interventions_complete` is recomputed rather than carried, because the
  stored `avg` was per-`schoolid`.
- The last version of each key keeps `9999-12-31`, matching what dbt leaves for
  a key its source no longer emits. AY2025 keys are in that state, since the
  rollup filters to `academic_year = {{ var("current_academic_year") }}`.
- The `schoolid` column is absent from the output, which is what lets the
  post-merge snapshot run insert by column name.

## Order of operations

The repair and the merge are coupled, but the gap between them fails safe: a
snapshot run against the un-repaired table errors on the column mismatch rather
than corrupting anything.

1. Merge the PR.
2. Run the repair `CREATE OR REPLACE` before the next `0 0 * * *` tick.
3. Confirm 0 duplicated student-week keys with the issue's reproduce query.
4. Report the shift in the published "% interventions complete" figure.

## Verification

- `uv run dbt build --select int_students__attendance_interventions_rollup+ --project-dir <worktree>/src/dbt/kipptaf`
- The issue's duplicate-key query against prod, before and after the repair:
  `duplicated` must go from 422,821 to 0 and `max_rows` from 354 to 1.
- Simulate the repaired table in a query and measure the before/after shift in
  the indicator, the way #5375 reported the 55.88% to 59.65% move, so the number
  change is stated rather than merged quietly.
- `trunk check --force --no-fix` on every changed file.

## Out of scope

The 6 remaining models on #5381 — `dibels_pm_weekly`,
`college_matriculation_weekly`, `dibels_benchmark_weekly`, `truancy_weekly`, the
4 discriminator-carrying models' residual duplicates, and
`star_assessment_weekly`'s empty result. Each has its own cause and gets its own
change. Diagnoses recorded on #5381.

The stale `/* DL school ID not unique, need a better crosswalk */` comment on
`int_students__attendance_interventions.sql:57`. The crosswalk is 1:1 against
current data, but that file is not otherwise touched here.
