# Put `int_powerschool__category_grades` on a daily cron and replace its `array_agg` dedupe

Design for #5213 (parent #5212). Brainstormed 2026-09-09. Numbers measured in
prod BigQuery the same day; re-measure before the PR.

## Decision

The issue names a join fan-out. The stage plan does not show one. In the latest
Newark run the storedgrades join took 6.89M rows in and put 6.89M out. The
142M-row read on that stage is BigQuery broadcasting the 1.3M-row
`stg_powerschool__storedgrades` to 100 workers, and the dedupe collapses the
enrollment-by-termbin expansion by 13%, not a storedgrades multiplication. Per
run the model costs about 26 slot-minutes in Newark.

What makes it 205 of the 221 weekly slot hours is cadence. Newark rebuilt the
table 478 times in 7 days (68 a day) on the eager table condition, because every
dlt pull of `cc`, `pgfinalgrades`, `students`, or `storedgrades` retriggers it.
Every consumer is a daily batch:

| Consumer                                                                 | Cadence (local) |
| ------------------------------------------------------------------------ | --------------- |
| `rpt_deanslist__final_grades` extract (reads the pivot)                  | 01:25 daily     |
| `int_students__category_grades` (kipptaf, cron)                          | 04:00 daily     |
| Tableau `gradebook_and_gpa_dashboard`, `academic_gradebook_health_suite` | 04:00 daily     |
| Tableau `gradebook_audit_teacher_report`                                 | Tue 07:30       |

Two changes, both in the `powerschool` package so Newark, Camden, and Paterson
move together:

1. A `0 0 * * *` cron on `int_powerschool__category_grades` and
   `int_powerschool__category_grades_pivot`. One build a day at local midnight,
   ahead of the 01:25 extract.
2. The `dbt_utils.deduplicate` call becomes a `row_number` pick. Measured on
   Newark prod tables with identical output: 12.1 slot-minutes for the current
   shape against 3.2 for the pick. The macro compiles to 16
   `array_agg(... limit 1)` columns, and BigQuery runs a partial aggregate for
   each inside the join stage plus a merge after it. One window sorts each
   partition once.

Expected result: Newark drops from about 205 slot hours a week to under 1.

## Cadence

In `src/dbt/powerschool/models/sis/intermediate/properties/`, both
`int_powerschool__category_grades.yml` and
`int_powerschool__category_grades_pivot.yml` gain:

```yaml
config:
  meta:
    dagster:
      automation_condition:
        cron_schedule: 0 0 * * *
```

The pivot yml already has `config.materialized: table`; the meta block nests
under that `config`. The category grades yml has no `config` block yet; its
materialization comes from each district's `dbt_project.yml`
(`powerschool: +materialized: table`), so the translator treats it as a table
and honors the cron.

No `cron_timezone`. The translator passes the code location's `LOCAL_TIMEZONE`.

Both models get a `description` that records the consumer cadences above and why
the tick is midnight, in the style of `int_students__category_grades.yml`. The
pivot shares the tick so `~any_deps_in_progress` serializes it after its parent.

Deploys still rebuild immediately: `code_version_changed` stays in the cron
condition.

## SQL

In
`src/dbt/powerschool/models/sis/intermediate/int_powerschool__category_grades.sql`,
the `deduplicate` CTE becomes two CTEs:

```sql
ranked as (
    select
        *,
        row_number() over (
            partition by studentid, yearid, course_number, storecode
            order by is_dropped_section asc, percent_grade desc
        ) as rn,
    from enr_gr
),

deduplicate as (select * except (rn), from ranked where rn = 1)
```

Same partition and order keys as the macro call, so the same pick, ties
included. Ties on `(is_dropped_section, percent_grade)` were already arbitrary
under `array_agg`, and stay arbitrary. This is a row pick (best section per
student, course, term, storecode), not dup masking, so the `row_number() = 1`
prohibition in `.claude/rules/dbt-sql.md` does not apply. The window lives in a
named column and the filter in the next CTE, per the no-`QUALIFY` rule.

The `-- trunk-ignore(sqlfluff/ST03)` above `enr_gr` comes off: the CTE is now
referenced directly. Output columns, contract, and tests do not change. The
`description` on the model gets one sentence naming the measured reason the
macro is not used here.

## Verification

Before merge, dbt Cloud CI builds the model into the PR schema. Compare against
`kippnewark_powerschool.int_powerschool__category_grades`:

- `count(*)` and
  `count(distinct format("%T|%T|%T|%T", studentid, yearid, course_number, storecode))`
  must match (6,078,717 both, measured 2026-09-09).
- `round(sum(percent_grade), 2)`, `round(sum(percent_grade_y1_running), 2)`,
  `countif(is_dropped_section)`, and `countif(is_current)` must match.
- `sum(sectionid)` and `count(citizenship_grade)` may differ by tie-breaking. A
  difference of more than 0.1% of rows means the pick changed and the PR is
  wrong.

After merge and the first midnight tick, re-run the ranking query from #5212 and
confirm Newark runs of this node dropped to about 1 a day. Confirm the new stage
plan has no `SHARD_ARRAY_AGG` step.

Post the corrected diagnosis on #5213 with the measurements above.

## Out of scope

- The storedgrades broadcast. At one build a day it costs under 2 slot-minutes.
- Incremental materialization by `yearid`. The package has no incremental
  models, and the saving at daily cadence is under 3 slot hours a week.
- The two `kippmiami_powerschool` runs seen today. #5208 already removed the
  package from Miami.
