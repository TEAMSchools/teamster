# kippadb snapshot boundary fan-out — design

Refs [#5381](https://github.com/TEAMSchools/teamster/issues/5381).

Covers `int_topline__college_matriculation_weekly` and
`int_topline__college_entrance_exams_weekly`. The other models on #5381 have
different causes and get their own changes.

## Problem

Both models repeat a student-week, and `int_topline__student_metrics` scores
each row, so a repeated student outweighs one that appears once.

Measured against prod on 2026-09-17:

| Model                                        | Grain tested                  | Duplicated | Disagreeing values | Most rows on one key |
| -------------------------------------------- | ----------------------------- | ---------- | ------------------ | -------------------- |
| `int_topline__college_matriculation_weekly`  | student-week                  | 173        | 172                | 2                    |
| `int_topline__college_entrance_exams_weekly` | student-week plus `test_type` | 183        | 183                | 2                    |

One cause in both, and it is the shape #5375 already fixed for the 2 GPA models.
Each model casts the snapshot's `dbt_valid_from` and `dbt_valid_to` to dates,
collapses same-day versions with `dbt_utils.deduplicate`, then matches
`week_start_monday between dbt_valid_from_date and dbt_valid_to_date`. A date
range is closed at both ends, so a version ending on the same date the next one
begins matches the same Monday twice.

The duplicates disagree on their values — 172 of 173 and 183 of 183 — so this
changes what each week reports, not only how much a student weighs.

## Design

Both models take the treatment `int_topline__gpa_term_weekly` now carries on
`main`, which follows `int_powerschool__gpa_term_lookback`:

- Delete the `deduplicate` CTE and both `cast(... as date)` columns.
- Add an `enrollment_weeks` CTE holding the model's filters and the boundary
  instant:
  `timestamp(date_add(week_end_sunday, interval 1 day), '{{ var("local_timezone") }}') as week_end_boundary`.
- Join half-open against the raw timestamps:
  `co.week_end_boundary > <snap>.dbt_valid_from and co.week_end_boundary <= <snap>.dbt_valid_to`.

The end-of-week anchor is the one #5375 settled with the metric owner, so every
topline weekly model agrees on what a week means.

### Dropping `deduplicate` is safe in both

#5375 could drop its `deduplicate` because the snapshot was contiguous in
timestamp space, meaning exactly one version matches any instant. Verified per
snapshot here, under each model's own filter:

| Snapshot                                                    | Versions | Overlapping | Gaps |
| ----------------------------------------------------------- | -------- | ----------- | ---- |
| `snapshot_kippadb__app_rollup`                              | 12,719   | 0           | 0    |
| `snapshot_kippadb__standardized_test_rollup`, joinable rows | 3,814    | 0           | 0    |
| `snapshot_kippadb__standardized_test_rollup`, NULL-id rows  | 16       | 14          | 0    |

The 14 overlapping versions all sit inside the 318 rows whose
`school_specific_id` is NULL. The join compares that column to `student_number`,
and NULL never matches, so those rows are unreachable — 0 of the 183 duplicates
trace to them.

### `int_topline__college_matriculation_weekly`

```sql
with
    enrollment_weeks as (
        select
            student_number,
            academic_year,
            week_start_monday,
            week_end_sunday,
            salesforce_id,

            /* first instant of the day AFTER the week closes, local — i.e. the
               value in effect at the END of the week */
            timestamp(
                date_add(week_end_sunday, interval 1 day), '{{ var("local_timezone") }}'
            ) as week_end_boundary,
        from {{ ref("int_extracts__student_enrollments_weeks") }}
        where
            is_enrolled_week
            and grade_level = 12
            and academic_year >= {{ var("current_academic_year") - 1 }}
    )

select
    co.student_number,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,

    m.is_submitted_ba,
    m.is_accepted_ba,
    m.is_matriculated_ba,
    m.is_submitted_quality_bar_4yr_int,
from enrollment_weeks as co
left join
    {{ ref("snapshot_kippadb__app_rollup") }} as m
    on co.salesforce_id = m.applicant
    and co.week_end_boundary > m.dbt_valid_from
    and co.week_end_boundary <= m.dbt_valid_to
```

The `LEFT JOIN` stays a left join. A 12th grader with no Salesforce application
record should keep a row with null metrics, which is what the model does today.

### `int_topline__college_entrance_exams_weekly`

```sql
with
    enrollment_weeks as (
        select
            student_number,
            academic_year,
            schoolid,
            week_start_monday,
            week_end_sunday,

            /* first instant of the day AFTER the week closes, local — i.e. the
               value in effect at the END of the week */
            timestamp(
                date_add(week_end_sunday, interval 1 day), '{{ var("local_timezone") }}'
            ) as week_end_boundary,
        from {{ ref("int_extracts__student_enrollments_weeks") }}
        where
            is_enrolled_week
            and school_level = 'HS'
            and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    sat_total as (
        select
            school_specific_id,
            test_type,
            score,
            dbt_valid_from,
            dbt_valid_to,
        from {{ ref("snapshot_kippadb__standardized_test_rollup") }}
        where
            test_type in ('SAT', 'PSAT NMSQT', 'PSAT 8/9')
            and test_subject = 'Combined'
            and score is not null
    )

select
    co.student_number,
    co.academic_year,
    co.schoolid,
    co.week_start_monday,
    co.week_end_sunday,

    sat.test_type,
    sat.score,
from enrollment_weeks as co
inner join
    sat_total as sat
    on co.student_number = sat.school_specific_id
    and co.week_end_boundary > sat.dbt_valid_from
    and co.week_end_boundary <= sat.dbt_valid_to
```

Two shape changes beyond the boundary fix, neither of which moves a row:

- The join becomes an explicit `inner join`. Today it is a `LEFT JOIN` with
  `sat.score is not null` in the `WHERE`, which drops every non-matching row
  anyway. Writing what it does removes the trap.
- `score is not null` moves into `sat_total`, where it filters the snapshot
  rather than reading as a filter on the preserved side of a left join.

The CTE keeps its name and still does real work, so it is not a pass-through
import CTE.

### Properties

Both files carry only `materialized: table` and the `#4153` cron comment today —
no description, no columns, no tests. Both gain:

- `dbt_utils.unique_combination_of_columns` at `config: severity: error`. The
  kipptaf project default is `warn`, which would not fail CI, and these are
  silent double-count defects.
  - `college_matriculation_weekly`: `student_number`, `academic_year`,
    `week_start_monday`.
  - `college_entrance_exams_weekly`: those 3 plus `test_type`.
- A model description and a description per column, matching the shape
  `int_topline__gpa_term_weekly.yml` uses on `main`.

The existing `materialized: table` and `cron_schedule: 0 0 * * *` stay
untouched.

## Measured shift

Simulated against prod by running each model's fixed SQL and comparing to the
live table.

`int_topline__college_matriculation_weekly`:

| Measure                  | Now    | Fixed  |
| ------------------------ | ------ | ------ |
| Rows                     | 32,996 | 32,823 |
| Duplicated student-weeks | 173    | 0      |
| Matriculated             | 6.41%  | 7.01%  |
| Accepted                 | 22.56% | 23.00% |

`int_topline__college_entrance_exams_weekly`:

| Measure                           | Now     | Fixed   |
| --------------------------------- | ------- | ------- |
| Rows                              | 120,808 | 122,688 |
| Duplicated student-week-test_type | 183     | 0       |
| SAT rows                          | 38,284  | 38,896  |
| Mean SAT score                    | 863.27  | 863.18  |

The entrance-exams row count rises by 1,880. That is the anchor moving from the
week's Monday to its close: a score first recorded mid-week now counts for the
week it arrived in, instead of waiting for the next one. It is the intended
effect of the end-of-week decision, not a regression.

## Verification

- `uv run dbt build --select int_topline__college_matriculation_weekly int_topline__college_entrance_exams_weekly --project-dir <worktree>/src/dbt/kipptaf`
- The issue's duplicate-key query against prod for both models: `duplicated`
  must reach 0 and `max_rows` 1.
- Re-run the shift simulation after the build and confirm it matches the table
  above, so the published numbers in the PR body are the ones that shipped.
- `trunk check --force --no-fix` on all 4 changed files.

## Out of scope

The 318 rows in `snapshot_kippadb__standardized_test_rollup` whose
`school_specific_id` is NULL. A NULL inside a composite `unique_key` stops dbt's
`unique_key_join_on` from ever matching, so those versions never close — the
same defect class as #5381's attendance snapshot, at 12 keys instead of 16,737.
They cause no duplicates in this model because the join cannot reach them, so
fixing them is a separate question with its own blast radius.

The remaining #5381 models: `truancy_weekly`, `dibels_pm_weekly`,
`dibels_benchmark_weekly`, `formative_assessment_weekly`'s residual, and
`star_assessment_weekly`. Diagnoses recorded on #5381.
